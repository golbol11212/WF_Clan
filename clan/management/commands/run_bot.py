"""
Rust+ бот для отслеживания статистики команды.

Запуск:
    python manage.py run_bot

Требования:
    pip install rustplus
"""

import asyncio
import logging

import discord
from asgiref.sync import sync_to_async
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

logger = logging.getLogger('rust_bot')


# ─── Вспомогательные функции ──────────────────────────────

def coords_to_grid(x, y, map_size):
    """Конвертирует координаты в обозначение квадрата карты (например 'B4', 'K12')."""
    cols = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    cell = map_size / 26
    col = min(int(x / cell), 25)
    row = min(int((map_size - y) / cell), 25)
    return f"{cols[col]}{row + 1}"


def fmt_time(seconds):
    """Форматирует секунды в читаемый вид: 90 → '1м 30с', 3700 → '1ч 1м'."""
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}с"
    elif seconds < 3600:
        return f"{seconds // 60}м {seconds % 60}с"
    else:
        return f"{seconds // 3600}ч {(seconds % 3600) // 60}м"


# ─── Django ORM (sync_to_async обёртки) ──────────────────

@sync_to_async
def db_get_active_configs():
    from clan.models import BotConfig
    return list(BotConfig.objects.filter(is_active=True))

@sync_to_async
def db_get_config_by_id(config_id):
    from clan.models import BotConfig
    return BotConfig.objects.filter(pk=config_id).first()

@sync_to_async
def db_get_city_zone(config_id):
    from clan.models import CityZone
    zone = CityZone.objects.filter(server_id=config_id).first()
    if not zone:
        zone = CityZone.objects.first()
    return zone

@sync_to_async
def db_get_or_create_player(steam_id, name):
    from clan.models import Player
    return Player.objects.get_or_create(steam_id=steam_id, defaults={'name': name})

@sync_to_async
def db_save(obj):
    obj.save()

@sync_to_async
def db_get_player(steam_id):
    from clan.models import Player
    return Player.objects.filter(steam_id=steam_id).first()

@sync_to_async
def db_find_player_by_name(name):
    from clan.models import Player
    return Player.objects.filter(name__icontains=name).first()

@sync_to_async
def db_create_death(player, x, y, grid, map_size):
    from clan.models import Death
    return Death.objects.create(player=player, x=x, y=y, grid_square=grid, map_size=map_size)

@sync_to_async
def db_get_deaths(player, limit=3):
    from clan.models import Death
    return list(Death.objects.filter(player=player).order_by('-timestamp')[:limit])

@sync_to_async
def db_count_deaths(player):
    from clan.models import Death
    return Death.objects.filter(player=player).count()

@sync_to_async
def db_get_online_players():
    from clan.models import Player
    return list(Player.objects.filter(is_online=True))

@sync_to_async
def db_get_all_players_by_city():
    from clan.models import Player
    return list(Player.objects.order_by('-total_city_seconds')[:10])

@sync_to_async
def db_get_all_players_for_status():
    from clan.models import Player, Death
    players = list(Player.objects.order_by('-is_online', '-total_online_seconds'))
    result = []
    for p in players:
        deaths = Death.objects.filter(player=p).count()
        result.append((p, deaths))
    return result


# ─── Команда управления ───────────────────────────────────

# Роли Discord у которых есть доступ к !!! рассылке
BROADCAST_ROLES = {'LEADER', 'LEADER TEAM 2', 'Staff', 'Caller'}


class Command(BaseCommand):
    help = 'Запускает Rust+ бота для отслеживания статистики команды'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._rust_socket     = None   # ссылка на активный RustSocket
        self._discord_channel = None   # последний канал где писали clan_stat / !!!
        # Время последнего исчезновения событий с карты {тип: datetime}
        self._event_last_seen = {}     # {5: datetime, 6: datetime, 8: datetime}

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Запуск Rust+ и Discord ботов...'))
        self.stdout.write('Для остановки нажмите Ctrl+C\n')
        try:
            asyncio.run(self._run_all())
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING('\nБоты остановлены (Ctrl+C).'))

    async def _run_all(self):
        """Запускает Discord бот + по одному Rust боту на каждый активный BotConfig."""
        configs = await db_get_active_configs()
        if not configs:
            self.stdout.write('[BOT] Нет активных BotConfig. Включи хотя бы один в /admin/')

        tasks = [asyncio.create_task(self._run_discord_bot())]
        for config in configs:
            tasks.append(asyncio.create_task(self._main_loop(config.pk)))

        # Если конфигов нет — всё равно запускаем Discord бота и ждём
        if not configs:
            tasks.append(asyncio.create_task(self._wait_for_configs()))

        await asyncio.gather(*tasks, return_exceptions=True)

    async def _wait_for_configs(self):
        """Ждёт появления активных конфигов и перезапускает при необходимости."""
        while True:
            await asyncio.sleep(30)
            configs = await db_get_active_configs()
            if configs:
                self.stdout.write('[BOT] Найдены активные конфиги — перезапуск...')
                for config in configs:
                    asyncio.create_task(self._main_loop(config.pk))
                break

    async def _main_loop(self, config_id):
        """Основной цикл для одного сервера — при ошибках переподключается через 10 сек."""
        while True:
            try:
                config = await db_get_config_by_id(config_id)
                if not config or not config.is_active:
                    logger.info(f'[{config_id}] Конфиг отключён. Ожидание...')
                    await asyncio.sleep(30)
                    continue
                await self._connect_and_run(config)
            except KeyboardInterrupt:
                raise
            except Exception as e:
                logger.error(f'[{config_id}] Критическая ошибка сессии: {e}', exc_info=True)
                logger.info(f'[{config_id}] Переподключение через 10 сек...')
                await asyncio.sleep(10)

    async def _run_discord_bot(self):
        """Discord бот — отвечает на 'клан статус' в любом канале."""
        token = getattr(settings, 'DISCORD_BOT_TOKEN', '')
        if not token:
            logger.warning('[DC] DISCORD_BOT_TOKEN не задан — Discord бот отключён.')
            return

        intents = discord.Intents.default()
        intents.message_content = True
        client = discord.Client(intents=intents)

        @client.event
        async def on_ready():
            msg = f'[DC] Discord бот запущен как {client.user}'
            logger.info(msg)
            self.stdout.write(msg)

        @client.event
        async def on_message(message):
            if message.author.bot:
                return
            text = message.content.strip()
            self._discord_channel = message.channel  # запоминаем канал

            if text.lower() == 'clan_stat':
                await self._send_discord_status(message.channel)

            elif text.startswith('!!!'):
                # Проверяем роль пользователя
                user_roles = {r.name for r in getattr(message.author, 'roles', [])}
                if user_roles & BROADCAST_ROLES:
                    await self._broadcast(None, text[3:].strip(), message.author.display_name, channel=message.channel)
                else:
                    await message.channel.send('У тебя нет прав для рассылки.')

        try:
            await client.start(token)
        except KeyboardInterrupt:
            await client.close()
        except Exception as e:
            self.stdout.write(f'[DC] Ошибка Discord бота: {e}')
            import traceback
            self.stdout.write(traceback.format_exc())

    async def _broadcast(self, socket, text, sender, channel=None):
        """Отправляет сообщение капсом 5 раз в Rust чат и в Discord."""
        if not text:
            return
        msg = text.upper()
        logger.info(f'[BROADCAST] {sender}: {msg}')

        # 5 раз в Rust чат
        rust_sock = socket or self._rust_socket
        if rust_sock:
            for _ in range(5):
                try:
                    await rust_sock.send_team_message(f'[{sender}] {msg}')
                    await asyncio.sleep(0.5)
                except Exception as e:
                    logger.error(f'[BROADCAST] Ошибка отправки в Rust: {e}')
                    break
        else:
            logger.warning('[BROADCAST] Rust сокет недоступен')

        # 5 раз в Discord
        dc_channel = channel or self._discord_channel
        if dc_channel:
            for _ in range(5):
                try:
                    await dc_channel.send(f'**[{sender}] {msg}**')
                    await asyncio.sleep(0.5)
                except Exception as e:
                    logger.error(f'[BROADCAST] Ошибка отправки в Discord: {e}')
                    break
        else:
            logger.warning('[BROADCAST] Discord канал недоступен')

    async def _send_discord_status(self, channel):
        """Отправляет статус команды embed-сообщением в Discord канал."""
        try:
            players = await db_get_all_players_for_status()

            if not players:
                await channel.send('Нет данных об игроках. Запусти бота: `python manage.py run_bot`')
                return

            embed = discord.Embed(
                title='WF | Статус команды',
                color=0x9b30ff,
            )

            online_count = sum(1 for p, _ in players if p.is_online)
            embed.description = f'Онлайн: **{online_count}/{len(players)}**'

            for player, deaths in players:
                status = '🟢' if player.is_online else '⚫'
                value = (
                    f'Онлайн: {fmt_time(player.total_online_seconds)} | '
                    f'Сити: {fmt_time(player.total_city_seconds)} | '
                    f'Смертей: {deaths} | '
                    f'АФК: {fmt_time(player.total_afk_seconds)}'
                )
                embed.add_field(
                    name=f'{status} {player.name}',
                    value=value,
                    inline=False,
                )

            from django.utils import timezone
            embed.set_footer(text=f'Обновлено: {timezone.localtime().strftime("%H:%M:%S")}')
            await channel.send(embed=embed)

        except Exception as e:
            logger.error(f'[DC] Ошибка отправки статуса: {e}', exc_info=True)
            await channel.send('[ERR] Не удалось получить статус.')

    async def _connect_and_run(self, config):
        """Одна сессия подключения к серверу Rust+."""
        from rustplus import RustSocket, ServerDetails
        from rustplus.annotations import TeamEvent, ChatEvent
        from rustplus.events import TeamEventPayload, ChatEventPayload

        config_updated_at = config.updated_at
        logger.info(f'Подключение к {config.ip}:{config.port} (steam_id={config.steam_id})...')

        # Создаём объект с данными сервера
        server = ServerDetails(
            str(config.ip),
            int(config.port),
            int(config.steam_id),
            int(config.player_token),
        )
        socket = RustSocket(server, use_fp_proxy=True)

        # Очищаем предыдущие обработчики событий при переподключении
        TeamEventPayload.HANDLER_LIST.unregister_all()
        ChatEventPayload.HANDLER_LIST.unregister_all()

        # Словарь: steam_id -> был ли жив на прошлой итерации (для отслеживания смертей)
        prev_alive: dict[int, bool] = {}

        # ── Обработчик изменения команды (смерти) ───────────
        @TeamEvent(server)
        async def on_team_changed(event):
            """Срабатывает при любом изменении в команде."""
            # Смерти теперь обрабатываются в polling-цикле (_check_deaths)
            pass

        # ── Обработчик командного чата ──────────────────────
        @ChatEvent(server)
        async def on_team_chat(event):
            """Срабатывает при получении сообщения в командном чате."""
            try:
                msg    = event.message           # RustChatMessage
                text   = str(msg.message).strip()
                sender = str(msg.name)
                logger.info(f'[ЧАТ] {sender}: {text}')
                if text.startswith('!!!'):
                    await self._broadcast(socket, text[3:].strip(), sender)
                elif text.startswith('!'):
                    await self._handle_command(socket, text, sender, _map_size[0])
            except Exception as e:
                logger.error(f'Ошибка обработчика chat: {e}', exc_info=True)

        # Подключаемся
        await socket.connect()
        self._rust_socket = socket
        logger.info('[OK] Подключён к серверу Rust+!')

        # Используем список из одного элемента как изменяемую ячейку для nonlocal в nested async
        _map_size = [await self._get_map_size(socket)]

        # ── Основной цикл опроса каждые 10 сек ──────────────
        iteration = 0
        try:
            while True:
                iteration += 1

                # Каждые 3 итерации (30 сек) проверяем изменение конфига в БД
                if iteration % 3 == 0:
                    new_cfg = await db_get_config_by_id(config.pk)
                    if new_cfg and new_cfg.updated_at != config_updated_at:
                        logger.info('[CFG] Конфиг изменился — переподключение...')
                        break

                # Отслеживаем события карты (heli/cargo/drop)
                try:
                    await self._track_map_events(socket)
                except Exception as e:
                    logger.error(f'Ошибка отслеживания событий карты: {e}')

                # Обновляем статистику команды + проверяем смерти
                try:
                    team = await socket.get_team_info()
                    if team and team.members is not None:
                        await self._check_deaths(team, prev_alive, socket, _map_size[0])
                        await self._update_team(team, _map_size[0], config.pk)
                except Exception as e:
                    logger.error(f'Ошибка получения team info: {e}', exc_info=True)

                await asyncio.sleep(10)

        except KeyboardInterrupt:
            raise
        finally:
            self._rust_socket = None
            try:
                await socket.disconnect()
                logger.info('[DISC] Отключён от сервера Rust+.')
            except Exception:
                pass

    async def _get_map_size(self, socket):
        """Получает размер карты с сервера."""
        try:
            map_info = await socket.get_map(
                add_icons=False,
                add_events=False,
                add_vending_machines=False,
                override_images={},
            )
            logger.info(f'[MAP] Размер карты: {map_info.width}')
            return map_info.width
        except Exception as e:
            logger.warning(f'Не удалось получить карту: {e}. Используем 4000 по умолчанию.')
            return 4000

    async def _track_map_events(self, socket):
        """Отслеживает появление/исчезновение событий карты каждые 10 сек."""
        markers = await socket.get_markers()
        now = timezone.now()
        active_types = {m.type for m in markers}
        # Типы: 5=CargoShip, 6=Crate(airdrop), 8=PatrolHeli
        for event_type in (5, 6, 8):
            if event_type not in active_types:
                # Событие исчезло — запоминаем время
                if event_type not in self._event_last_seen:
                    self._event_last_seen[event_type] = now
            else:
                # Событие активно — сбрасываем таймер
                self._event_last_seen.pop(event_type, None)

    async def _check_deaths(self, team, prev_alive, socket, map_size):
        """Проверяет смерти игроков по данным из polling-цикла."""
        for member in team.members:
            sid      = int(member.steam_id)
            is_alive = bool(member.is_alive)
            was_alive = prev_alive.get(sid, True)

            if was_alive and not is_alive:
                player = await db_get_player(sid)
                if player:
                    x    = player.last_x or 0.0
                    y    = player.last_y or 0.0
                    grid = coords_to_grid(x, y, map_size)
                    await db_create_death(player, x, y, grid, map_size)
                    logger.info(f'[DEATH] {player.name} @ {grid}')
                    try:
                        await socket.send_team_message(
                            f"[RIP] {player.name} умер в квадрате {grid}"
                        )
                    except Exception as e:
                        logger.error(f'Ошибка отправки сообщения о смерти: {e}')

            prev_alive[sid] = is_alive

    async def _update_team(self, team, map_size, config_id):
        """Обновляет статистику всех участников команды из team info."""
        city_zone = await db_get_city_zone(config_id)
        now = timezone.now()

        for member in team.members:
            steam_id  = int(member.steam_id)
            is_online = bool(member.is_online)
            x         = float(member.x)
            y         = float(member.y)
            name      = str(member.name)

            player, created = await db_get_or_create_player(steam_id, name)
            if created:
                logger.info(f'[NEW] Новый игрок в команде: {name} [{steam_id}]')

            was_online    = player.is_online
            player.is_online = is_online

            if is_online:
                player.last_seen = now

                # Обновляем имя если изменилось (смена ника)
                if player.name != name:
                    logger.info(f'[RENAME]: {player.name} → {name}')
                    player.name = name

                # Определяем движение: изменение позиции > 2 единицы
                if player.last_x is not None and player.last_y is not None:
                    if abs(x - player.last_x) > 2 or abs(y - player.last_y) > 2:
                        player.last_move_time = now
                elif player.last_move_time is None:
                    player.last_move_time = now  # Первая фиксация позиции

                player.last_x = x
                player.last_y = y

                # Фиксируем начало сессии
                if not was_online:
                    player.session_start = now
                    logger.info(f'[+] {name} зашёл на сервер')

                # Накапливаем онлайн-время (интервал опроса = 10 сек)
                player.total_online_seconds += 10

                # АФК: нет движения 300+ секунд
                if player.last_move_time:
                    afk_sec = (now - player.last_move_time).total_seconds()
                    if afk_sec >= 300:
                        player.total_afk_seconds += 10

                # Время в зоне City
                if city_zone and city_zone.contains(x, y):
                    player.total_city_seconds += 10

            else:
                if was_online:
                    player.session_start = None
                    logger.info(f'[-] {name} вышел с сервера')

            await db_save(player)

        logger.debug(f'Обновлена статистика {len(team.members)} игроков')

    async def _handle_command(self, socket, text, sender, map_size):
        """Обрабатывает команды командного чата (начинающиеся с '!')."""
        parts = text.split()
        cmd   = parts[0].lower()
        logger.info(f'[КОМАНДА] {sender}: {cmd}')

        try:
            # ── !time ─────────────────────────────────────────
            if cmd == '!time':
                t = await socket.get_time()
                # RustTime: .time (str), .day_length (float мин), .sunrise/.sunset
                await socket.send_team_message(
                    f"Время: {t.time} | День: {t.day_length:.0f}м"
                )

            # ── !stats [@ник] ──────────────────────────────────
            elif cmd == '!stats':
                target = parts[1].lstrip('@') if len(parts) > 1 else sender
                player = await db_find_player_by_name(target)
                if not player:
                    await socket.send_team_message(f"[ERR] Игрок '{target}' не найден")
                    return
                deaths = await db_count_deaths(player)
                await socket.send_team_message(
                    f"{player.name} | "
                    f"Онлайн: {fmt_time(player.total_online_seconds)} | "
                    f"Сити: {fmt_time(player.total_city_seconds)} | "
                    f"Смертей: {deaths} | "
                    f"АФК: {fmt_time(player.total_afk_seconds)}"
                )

            # ── !deaths [@ник] ─────────────────────────────────
            elif cmd == '!deaths':
                target = parts[1].lstrip('@') if len(parts) > 1 else sender
                player = await db_find_player_by_name(target)
                if not player:
                    await socket.send_team_message(f"[ERR] Игрок '{target}' не найден")
                    return
                deaths = await db_get_deaths(player, limit=3)
                if not deaths:
                    await socket.send_team_message(f"[D] {player.name}: смертей нет")
                    return
                lines = [f"[D] Смерти {player.name}:"]
                for d in deaths:
                    lines.append(
                        f"[{d.timestamp.strftime('%H:%M')}] квадрат {d.grid_square} ({d.x:.0f}, {d.y:.0f})"
                    )
                await socket.send_team_message('\n'.join(lines))

            # ── !afk ───────────────────────────────────────────
            elif cmd == '!afk':
                now    = timezone.now()
                online = await db_get_online_players()
                afk_list = []
                for p in online:
                    if p.last_move_time:
                        afk_sec = int((now - p.last_move_time).total_seconds())
                        if afk_sec >= 300:
                            afk_list.append(f"{p.name} ({fmt_time(afk_sec)})")
                if afk_list:
                    await socket.send_team_message(f"АФК: {', '.join(afk_list)}")
                else:
                    await socket.send_team_message("АФК игроков нет")

            # ── !city ──────────────────────────────────────────
            elif cmd == '!city':
                players = await db_get_all_players_by_city()
                if not players:
                    await socket.send_team_message("Нет данных о времени в City")
                    return
                lines = [f"{p.name}: {fmt_time(p.total_city_seconds)}" for p in players]
                await socket.send_team_message(f"Время в сити: {', '.join(lines)}")

            # ── !where @ник ────────────────────────────────────
            elif cmd == '!where':
                if len(parts) < 2:
                    await socket.send_team_message("[ERR] Использование: !where @ник")
                    return
                target = parts[1].lstrip('@')
                player = await db_find_player_by_name(target)
                if not player:
                    await socket.send_team_message(f"[ERR] Игрок '{target}' не найден")
                    return
                if player.last_x is None or player.last_y is None:
                    await socket.send_team_message(f"{player.name}: позиция неизвестна")
                    return
                grid = coords_to_grid(player.last_x, player.last_y, map_size)
                await socket.send_team_message(
                    f"{player.name} → квадрат {grid} ({player.last_x:.0f}, {player.last_y:.0f})"
                )

            # ── !drop / !cargo / !heli ────────────────────────
            elif cmd in ('!drop', '!cargo', '!heli'):
                try:
                    markers = await socket.get_markers()
                except Exception:
                    await socket.send_team_message("[ERR] Не удалось получить маркеры карты")
                    return

                event_map = {'!drop': (6, 'DROP', 'Аирдроп'),
                             '!cargo': (5, 'CARGO', 'Карго'),
                             '!heli': (8, 'HELI', 'Вертолёт')}
                etype, tag, label = event_map[cmd]
                found = [m for m in markers if m.type == etype]

                if found:
                    locs = ', '.join(coords_to_grid(m.x, m.y, map_size) for m in found)
                    await socket.send_team_message(f"[{tag}] {label} на карте: {locs}")
                else:
                    last = self._event_last_seen.get(etype)
                    if last:
                        mins = int((timezone.now() - last).total_seconds() / 60)
                        await socket.send_team_message(
                            f"[{tag}] {label} нет на карте. Пропал {mins} мин назад."
                        )
                    else:
                        await socket.send_team_message(
                            f"[{tag}] {label} нет на карте. Время появления неизвестно."
                        )

            # ── !help ──────────────────────────────────────────
            elif cmd == '!help':
                await socket.send_team_message(
                    "Команды бота:\n"
                    "!time — время сервера\n"
                    "!stats [@ник] — статистика игрока\n"
                    "!deaths [@ник] — последние 3 смерти\n"
                    "!afk — кто сейчас АФК\n"
                    "!city — время в зоне City\n"
                    "!where @ник — местоположение игрока\n"
                    "!drop — аирдроп на карте\n"
                    "!cargo — карго корабль\n"
                    "!heli — патрульный вертолёт"
                )

        except Exception as e:
            logger.error(f'Ошибка команды "{cmd}": {e}', exc_info=True)
            try:
                await socket.send_team_message("[ERR] Ошибка при выполнении команды")
            except Exception:
                pass
