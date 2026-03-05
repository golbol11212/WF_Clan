import urllib.request
import urllib.error
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .models import Application, Member, WipePost, UserProfile
from .serializers import ApplicationSerializer


def fetch_steam_name(steam_url: str) -> str:
    """Возвращает Steam-ник из публичного профиля через Community XML API."""
    url = steam_url.strip().rstrip('/')
    if not url:
        return ''
    # Принимаем: steamcommunity.com/id/xxx  или  steamcommunity.com/profiles/76561...
    # Или просто короткий ID/никнейм — оборачиваем в /id/
    if not url.startswith('http'):
        url = 'https://steamcommunity.com/id/' + url
    xml_url = url + '/?xml=1'
    try:
        req = urllib.request.Request(xml_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as resp:
            tree = ET.fromstring(resp.read())
            name = tree.findtext('steamID')
            return (name or '').strip()
    except Exception:
        return ''


def send_discord_webhook(application):
    """Отправляет embed с заявкой в Discord через webhook."""
    url = getattr(settings, 'DISCORD_WEBHOOK_URL', None)
    if not url:
        return

    role_labels = {
        'raider':  'Raider',
        'builder': 'Builder / Electrician',
        'pvp':     'PVP / Coller',
        'farmer':  'Farmer / Support',
        'any':     'Any',
    }
    region_flag = {'EU': '🇪🇺', 'RU': '🇷🇺', 'NA': '🇺🇸', 'ASIA': '🌏'}

    payload = {
        "embeds": [{
            "title": "📋 Новая заявка в клан WF",
            "color": 0xFF4400,
            "fields": [
                {"name": "Steam",        "value": application.steam_name,                               "inline": True},
                {"name": "Discord",      "value": application.discord_tag,                              "inline": True},
                {"name": "Часов в Rust", "value": str(application.hours),                               "inline": True},
                {"name": "Регион",       "value": f"{region_flag.get(application.region, '')} {application.region}", "inline": True},
                {"name": "Роль",         "value": role_labels.get(application.role, application.role),  "inline": True},
                {"name": "Почему хочет", "value": application.reason[:1024]},
            ],
            "footer": {"text": f"WF Clan • Заявка #{application.id}"},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }]
    }

    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={
        'Content-Type': 'application/json',
        'User-Agent': 'DiscordBot (WF-Clan, 1.0)',
    }, method='POST')
    try:
        urllib.request.urlopen(req, timeout=5)
    except urllib.error.URLError:
        pass  # не блокируем API если Discord недоступен

def _post_to_discord(webhook_key: str, payload: dict):
    """Отправляет payload в Discord webhook. webhook_key — имя ключа в settings."""
    url = getattr(settings, webhook_key, None)
    if not url:
        return
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={
        'Content-Type': 'application/json',
        'User-Agent': 'DiscordBot (WF-Clan, 1.0)',
    }, method='POST')
    try:
        urllib.request.urlopen(req, timeout=5)
    except urllib.error.URLError:
        pass


def send_wipe_webhook(wipe, old_message_id: str = '') -> str:
    """Постит вайп в Discord. Если old_message_id передан — сначала удаляет старое сообщение.
    Возвращает ID нового сообщения (или '' при ошибке)."""
    url = getattr(settings, 'DISCORD_CLAN_WEBHOOK_URL', None)
    if not url:
        return ''

    # Удаляем предыдущее сообщение вайпа
    if old_message_id:
        delete_url = url + f'/messages/{old_message_id}'
        req = urllib.request.Request(delete_url, method='DELETE', headers={
            'User-Agent': 'DiscordBot (WF-Clan, 1.0)',
        })
        try:
            urllib.request.urlopen(req, timeout=5)
        except urllib.error.URLError:
            pass

    squad_names = ', '.join(
        m.display_name() for m in wipe.squad.filter(is_active=True)[:20]
    ) or '—'
    wipe_dt = wipe.wipe_date.strftime('%d.%m.%Y %H:%M МСК') if wipe.wipe_date else '—'

    fields = [
        {"name": "🖥️ Сервер",     "value": wipe.server_name,      "inline": True},
        {"name": "📅 Дата вайпа",  "value": wipe_dt,               "inline": True},
        {"name": "🔌 Коннект",     "value": f"`{wipe.connect}`",   "inline": False},
        {"name": "⚔️ Рейд",        "value": wipe.raid_plan or '—', "inline": False},
        {"name": "👥 Состав",      "value": squad_names,           "inline": False},
    ]
    if wipe.description:
        fields.append({"name": "📝 Описание", "value": wipe.description[:1024], "inline": False})

    payload = {
        "embeds": [{
            "title": f"🗺️ {wipe.title}",
            "color": 0x9B30FF,
            "fields": fields,
            "footer": {"text": f"WF Clan • Вайп #{wipe.id}"},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }]
    }

    # ?wait=true — Discord вернёт JSON с id сообщения
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url + '?wait=true', data=data, headers={
        'Content-Type': 'application/json',
        'User-Agent': 'DiscordBot (WF-Clan, 1.0)',
    }, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            result = json.loads(resp.read())
            return result.get('id', '')
    except urllib.error.URLError:
        return ''


def send_roster_webhook() -> str:
    """Постит актуальный состав клана в Discord. Возвращает ID нового сообщения."""
    from .models import Member, DiscordMessage

    url = getattr(settings, 'DISCORD_ROSTER_WEBHOOK_URL', None)
    if not url:
        return ''

    # Удаляем предыдущее сообщение ростера
    record, _ = DiscordMessage.objects.get_or_create(key='roster')
    if record.message_id:
        delete_url = url + f'/messages/{record.message_id}'
        req = urllib.request.Request(delete_url, method='DELETE', headers={
            'User-Agent': 'DiscordBot (WF-Clan, 1.0)',
        })
        try:
            urllib.request.urlopen(req, timeout=5)
        except urllib.error.URLError:
            pass

    rank_icon = {
        'leader':    '👑',
        'co-leader': '🥈',
        'veteran':   '⭐',
        'member':    '🔹',
        'recruit':   '🔸',
    }
    spec_icon = {
        'raider':  '💣',
        'builder': '🔧',
        'pvp':     '⚔️',
        'farmer':  '⛏️',
        'any':     '❓',
    }

    members = Member.objects.filter(is_active=True).select_related('user', 'user__profile').order_by('order', 'nickname')
    total = members.count()

    # Группируем по рангу для красивого вывода
    groups = {}
    rank_order = ['leader', 'co-leader', 'veteran', 'member', 'recruit']
    for m in members:
        groups.setdefault(m.rank, []).append(m)

    fields = []
    for rank in rank_order:
        if rank not in groups:
            continue
        lines = []
        for m in groups[rank]:
            icon = spec_icon.get(m.specialization, '❓')
            hours_str = f' · {m.hours}ч' if m.hours else ''
            lines.append(f'{icon} **{m.display_name()}**{hours_str}')
        fields.append({
            "name": f"{rank_icon.get(rank, '')} {rank.upper()} ({len(groups[rank])})",
            "value": '\n'.join(lines) or '—',
            "inline": True,
        })

    payload = {
        "embeds": [{
            "title": f"👥 Состав клана WF — {total} игроков",
            "color": 0x9B30FF,
            "fields": fields,
            "footer": {"text": "WF Clan • Состав обновлён"},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }]
    }

    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url + '?wait=true', data=data, headers={
        'Content-Type': 'application/json',
        'User-Agent': 'DiscordBot (WF-Clan, 1.0)',
    }, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            result = json.loads(resp.read())
            new_id = result.get('id', '')
            record.message_id = new_id
            record.save()
            return new_id
    except urllib.error.URLError:
        return ''


def send_register_webhook(username: str, steam_name: str, role: str, hours: int):
    """Уведомление о новой регистрации."""
    role_labels = {
        'raider': 'Raider', 'builder': 'Builder / Electrician',
        'pvp': 'PVP / Coller', 'farmer': 'Farmer / Support', 'any': 'Any',
    }
    payload = {
        "embeds": [{
            "title": "👤 Новый игрок зарегистрировался",
            "color": 0x00AAFF,
            "fields": [
                {"name": "Аккаунт",     "value": username,                         "inline": True},
                {"name": "Steam",       "value": steam_name or '—',                "inline": True},
                {"name": "Роль",        "value": role_labels.get(role, role),       "inline": True},
                {"name": "Часов в Rust","value": str(hours) if hours else '—',     "inline": True},
            ],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }]
    }
    _post_to_discord('DISCORD_CLAN_WEBHOOK_URL', payload)


# ── СТАТИЧНЫЕ ДАННЫЕ (можно вынести в БД позже) ──────────────

SERVERS = [
    {"id": 1, "name": "WF | EU MAIN — VANILLA x1",      "type": "vanilla",  "status": "online",  "players": 186, "max_players": 200, "ping": 18,   "wipe_day": "ЧТ 20:00",        "region": "EU-WEST"},
    {"id": 2, "name": "WF | EU MODDED — x2 GATHER",     "type": "modded",   "status": "online",  "players": 78,  "max_players": 150, "ping": 22,   "wipe_day": "ПТ 19:00",        "region": "EU-WEST"},
    {"id": 3, "name": "WF | TRAINING — AIM & ELECTRIC",  "type": "training", "status": "online",  "players": 20,  "max_players": 50,  "ping": 34,   "wipe_day": "—",               "region": "EU-WEST"},
    {"id": 4, "name": "WF | EU MAIN 2 — VANILLA x1",    "type": "vanilla",  "status": "offline", "players": 0,   "max_players": 200, "ping": None, "wipe_day": "СЛЕДУЮЩИЙ ВАЙП", "region": "EU-EAST"},
]

ACHIEVEMENTS = [
    {"id": 1, "icon": "🏆", "stat": "TOP 1", "name": "Facepunch Official",       "description": "Первое место на официальном сервере Facepunch EU. Доминировали весь вайп без потери главной базы.",                   "tier": "gold"},
    {"id": 2, "icon": "💀", "stat": "50+",   "name": "Successful Raids",         "description": "Более 50 успешных рейдов за последний сезон. Средняя длительность рейда — 18 минут.",                                  "tier": "default"},
    {"id": 3, "icon": "🏚️", "stat": "12×",   "name": "Wipe Dominators",          "description": "12 вайпов подряд с полным контролем карты к концу первого дня. Рекорд среди RU кланов.",                              "tier": "default"},
    {"id": 4, "icon": "⚡", "stat": "2:47",  "name": "Fastest Full Online Raid", "description": "Рекорд скорости рейда онлайн базы уровня T3 — 2 минуты 47 секунд от первого взрыва до лута.",                        "tier": "default"},
    {"id": 5, "icon": "🛡️", "stat": "0",     "name": "Bases Lost This Season",   "description": "Ноль потерянных баз за текущий сезон. Наши билдеры и электрики обеспечивают абсолютную защиту.",                     "tier": "default"},
    {"id": 6, "icon": "👑", "stat": "#1",    "name": "RU Clan Rankings",         "description": "Лучший русскоязычный клан по версии Rust Community Awards 2024. Голосование 14 000+ участников.",                     "tier": "gold"},
]

VIDEOS = [
    {"id": 1, "title": "РЕЙД БАЗЫ Т4 — ONLINE RAID 2025",         "category": "raid",  "duration": "18:34", "views": "847K",  "date": "12 ЯНВ 2025"},
    {"id": 2, "title": "COLLER vs 10 PLAYERS — NO CLIP",           "category": "pvp",   "duration": "12:08", "views": "520K",  "date": "5 ФЕВ 2025"},
    {"id": 3, "title": "МЕГА БАЗА — BUNKER + ЭЛЕКТРИКА 2025",      "category": "build", "duration": "28:45", "views": "312K",  "date": "20 ЯНВ 2025"},
    {"id": 4, "title": "ГАЙД: ЭЛЕКТРИКА ДЛЯ НОВИЧКОВ 2025",       "category": "guide", "duration": "22:17", "views": "680K",  "date": "3 МАР 2025"},
    {"id": 5, "title": "САМЫЙ БЫСТРЫЙ РЕЙД — 2:47 WORLD RECORD",  "category": "raid",  "duration": "35:02", "views": "1.1M",  "date": "15 МАЙ 2024"},
    {"id": 6, "title": "WF COLLERS — WIPE DAY PVP MONTAGE",        "category": "pvp",   "duration": "09:51", "views": "290K",  "date": "28 ФЕВ 2025"},
]

# ── API VIEWS ─────────────────────────────────────────────────

@api_view(['GET'])
def stats(request):
    online  = sum(1 for s in SERVERS if s['status'] == 'online')
    players = sum(s['players'] for s in SERVERS)
    return Response({
        "members":        247,
        "win_rate":       89,
        "years_active":   4,
        "raids_won":      1200,
        "global_rank":    "#03",
        "servers_online": online,
        "total_players":  players,
    })


@api_view(['GET'])
def servers(request):
    return Response(SERVERS)


@api_view(['GET'])
def achievements(request):
    return Response(ACHIEVEMENTS)


@api_view(['GET'])
def videos(request):
    return Response(VIDEOS)


@api_view(['GET'])
def roster(request):
    qs = Member.objects.filter(is_active=True).select_related('user', 'user__profile')
    data = []
    for m in qs:
        data.append({
            'id':             m.id,
            'nickname':       m.display_name(),
            'rank':           m.rank,
            'specialization': m.specialization,
            'region':         m.region,
            'hours':          m.hours,
            'avatar_url':     m.avatar_url,
            'discord_tag':    m.discord_tag,
            'join_date':      m.join_date,
        })
    return Response(data)


def _serialize_wipe(wipe):
    squad = []
    for m in wipe.squad.filter(is_active=True).select_related('user', 'user__profile'):
        squad.append({
            'id':             m.id,
            'nickname':       m.display_name(),
            'rank':           m.rank,
            'specialization': m.specialization,
            'avatar_url':     m.avatar_url,
        })
    return {
        'id':          wipe.id,
        'title':       wipe.title,
        'server_name': wipe.server_name,
        'connect':     wipe.connect,
        'wipe_date':   wipe.wipe_date.isoformat() if wipe.wipe_date else None,
        'raid_plan':   wipe.raid_plan,
        'description': wipe.description,
        'is_active':   wipe.is_active,
        'created_at':  wipe.created_at.isoformat(),
        'squad':       squad,
    }


@api_view(['GET'])
def wipe_current(request):
    wipe = WipePost.objects.filter(is_active=True).prefetch_related('squad').first()
    if not wipe:
        return Response({'ok': False, 'wipe': None})
    return Response({'ok': True, 'wipe': _serialize_wipe(wipe)})


@api_view(['GET'])
def wipe_archive(request):
    wipes = WipePost.objects.filter(is_active=False).prefetch_related('squad')[:10]
    return Response([_serialize_wipe(w) for w in wipes])


@api_view(['POST'])
def apply(request):
    serializer = ApplicationSerializer(data=request.data)
    if serializer.is_valid():
        application = serializer.save()
        send_discord_webhook(application)
        return Response(
            {"ok": True, "message": "Заявка принята! Мы свяжемся с тобой в Discord.", "id": serializer.data['id']},
            status=status.HTTP_201_CREATED,
        )
    return Response({"ok": False, "errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
def register(request):
    username   = request.data.get('username', '').strip()
    email      = request.data.get('email', '').strip()
    password   = request.data.get('password', '')
    steam_url  = request.data.get('steam_url', '').strip()
    role       = request.data.get('role', 'any')
    hours      = int(request.data.get('hours', 0) or 0)

    if len(username) < 3:
        return Response({"ok": False, "error": "Никнейм должен содержать минимум 3 символа"}, status=400)
    if not email or '@' not in email:
        return Response({"ok": False, "error": "Введите корректный email"}, status=400)
    if len(password) < 8:
        return Response({"ok": False, "error": "Пароль должен содержать минимум 8 символов"}, status=400)
    if User.objects.filter(username=username).exists():
        return Response({"ok": False, "error": "Никнейм уже занят"}, status=400)
    if User.objects.filter(email=email).exists():
        return Response({"ok": False, "error": "Email уже используется"}, status=400)

    # Получаем Steam-ник (если указан URL)
    steam_name = ''
    if steam_url:
        steam_name = fetch_steam_name(steam_url)

    valid_roles = {'raider', 'builder', 'pvp', 'farmer', 'any'}
    if role not in valid_roles:
        role = 'any'

    user = User.objects.create_user(username=username, email=email, password=password)
    UserProfile.objects.create(user=user, steam_name=steam_name, steam_url=steam_url, role=role, hours=hours)
    token, _ = Token.objects.get_or_create(user=user)
    send_register_webhook(username, steam_name, role, hours)
    return Response(
        {"ok": True, "message": "Аккаунт создан!", "token": token.key,
         "username": user.username, "steam_name": steam_name},
        status=status.HTTP_201_CREATED,
    )


@api_view(['GET'])
def user_info(request):
    """Возвращает профиль юзера для автозаполнения в MemberAdmin."""
    user_id = request.query_params.get('user_id', '').strip()
    if not user_id:
        return Response({'ok': False}, status=400)
    try:
        profile = UserProfile.objects.select_related('user').get(user_id=user_id)
        return Response({
            'ok':         True,
            'steam_name': profile.steam_name,
            'role':       profile.role,
            'hours':      profile.hours,
        })
    except UserProfile.DoesNotExist:
        return Response({'ok': False, 'error': 'Профиль не найден'}, status=404)


@api_view(['GET'])
def steam_lookup(request):
    """Возвращает Steam-ник по URL профиля (без регистрации)."""
    url = request.query_params.get('url', '').strip()
    if not url:
        return Response({'ok': False, 'error': 'URL не указан'}, status=400)
    name = fetch_steam_name(url)
    if not name:
        return Response({'ok': False, 'error': 'Профиль не найден или закрыт'}, status=404)
    return Response({'ok': True, 'steam_name': name})


@api_view(['POST'])
def login_view(request):
    identifier = request.data.get('username', '').strip()
    password   = request.data.get('password', '')

    if not identifier or not password:
        return Response({"ok": False, "error": "Введите никнейм и пароль"}, status=400)

    user = authenticate(username=identifier, password=password)
    if not user:
        # Попытка входа по email
        try:
            u = User.objects.get(email=identifier)
            user = authenticate(username=u.username, password=password)
        except User.DoesNotExist:
            pass

    if not user:
        return Response({"ok": False, "error": "Неверный никнейм/email или пароль"}, status=401)

    token, _ = Token.objects.get_or_create(user=user)
    return Response({"ok": True, "token": token.key, "username": user.username})
