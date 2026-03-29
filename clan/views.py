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
from .models import Application, Member, WipePost, UserProfile, Server, Video
from .serializers import ApplicationSerializer


MONTHS_RU = ['ЯНВ','ФЕВ','МАР','АПР','МАЙ','ИЮН','ИЮЛ','АВГ','СЕН','ОКТ','НОЯ','ДЕК']


def _parse_yt_duration(iso: str) -> str:
    """PT18M34S → '18:34', PT2H5M3S → '2:05:03'"""
    import re
    m = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', iso)
    if not m:
        return ''
    h, mn, s = (int(x) if x else 0 for x in m.groups())
    return f'{h}:{mn:02d}:{s:02d}' if h else f'{mn}:{s:02d}'


def _fmt_views(n_str: str) -> str:
    """'847234' → '847K', '1100000' → '1.1M'"""
    n = int(n_str)
    if n >= 1_000_000:
        v = n / 1_000_000
        s = f'{v:.1f}'.rstrip('0').rstrip('.')
        return f'{s}M'
    if n >= 1_000:
        return f'{round(n / 1_000)}K'
    return str(n)


def _fmt_date_ru(iso: str) -> str:
    """'2025-01-12T10:00:00Z' → '12 ЯНВ 2025'"""
    from datetime import datetime as dt
    d = dt.fromisoformat(iso.replace('Z', '+00:00'))
    return f'{d.day} {MONTHS_RU[d.month - 1]} {d.year}'


def fetch_video_meta(url: str) -> dict:
    """Подтягивает метаданные видео с YouTube или TikTok по ссылке.
    Для YouTube просмотры/длительность/дата требуют YOUTUBE_API_KEY в settings.
    Без ключа возвращает только название (через oEmbed)."""
    import re, urllib.parse
    result = {'title': '', 'duration': '', 'views': '', 'date': '', 'thumbnail_url': ''}

    # ── YouTube ──────────────────────────────────────────────
    m = re.search(
        r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([A-Za-z0-9_-]{11})',
        url,
    )
    if m:
        vid = m.group(1)
        api_key = getattr(settings, 'YOUTUBE_API_KEY', '')
        # Превью YouTube — всегда доступно без ключа
        result['thumbnail_url'] = f'https://img.youtube.com/vi/{vid}/hqdefault.jpg'
        if api_key:
            api_url = (
                'https://www.googleapis.com/youtube/v3/videos'
                f'?part=snippet,contentDetails,statistics&id={vid}&key={api_key}'
            )
            try:
                req = urllib.request.Request(api_url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=6) as resp:
                    data = json.loads(resp.read())
                    items = data.get('items', [])
                    if items:
                        it = items[0]
                        result['title']    = it['snippet']['title']
                        result['duration'] = _parse_yt_duration(it['contentDetails']['duration'])
                        result['views']    = _fmt_views(it['statistics'].get('viewCount', '0'))
                        result['date']     = _fmt_date_ru(it['snippet']['publishedAt'])
                        # Лучшее превью из API
                        thumbs = it['snippet'].get('thumbnails', {})
                        for q in ('maxres', 'standard', 'high', 'medium', 'default'):
                            if q in thumbs:
                                result['thumbnail_url'] = thumbs[q]['url']
                                break
            except Exception:
                pass
        else:
            # Без API-ключа — название через oEmbed (URL нужно экранировать)
            try:
                video_url = urllib.parse.quote(
                    f'https://www.youtube.com/watch?v={vid}', safe=''
                )
                oe = f'https://www.youtube.com/oembed?url={video_url}&format=json'
                req = urllib.request.Request(oe, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=5) as resp:
                    data = json.loads(resp.read())
                    result['title'] = data.get('title', '')
                    if data.get('thumbnail_url'):
                        result['thumbnail_url'] = data['thumbnail_url']
            except Exception:
                pass
        return result

    # ── TikTok ───────────────────────────────────────────────
    if 'tiktok.com' in url:
        try:
            encoded = urllib.parse.quote(url, safe='')
            oe = f'https://www.tiktok.com/oembed?url={encoded}'
            req = urllib.request.Request(oe, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
                result['title'] = data.get('title', '')
                if data.get('thumbnail_url'):
                    result['thumbnail_url'] = data['thumbnail_url']
        except Exception:
            pass

    return result


def fetch_steam_data(steam_url: str) -> dict:
    """Возвращает dict с ключами 'name' и 'avatar_url' из публичного профиля Steam (Community XML API)."""
    url = steam_url.strip().rstrip('/')
    if not url:
        return {'name': '', 'avatar_url': ''}
    if not url.startswith('http'):
        url = 'https://steamcommunity.com/id/' + url
    xml_url = url + '/?xml=1'
    try:
        req = urllib.request.Request(xml_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as resp:
            tree = ET.fromstring(resp.read())
            name       = (tree.findtext('steamID') or '').strip()
            avatar_url = (tree.findtext('avatarFull') or '').strip()
            return {'name': name, 'avatar_url': avatar_url}
    except Exception:
        return {'name': '', 'avatar_url': ''}


def fetch_steam_name(steam_url: str) -> str:
    """Совместимая обёртка — возвращает только Steam-ник."""
    return fetch_steam_data(steam_url)['name']


def send_discord_webhook(application):
    """Отправляет embed с заявкой в Discord через webhook."""
    url = getattr(settings, 'DISCORD_WEBHOOK_URL', None)
    if not url:
        return

    role_labels = {
        'leader':   'Лидер',
        'deputy':   'Зам',
        'coller':   'Колер',
        'builder':  'Билдер',
        'electric': 'Электрик',
        'farmer':   'Фармер',
        'combater': 'Комбатер',
        'raider':   'Рейдер',
        'ferm':     'Фермер',
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
        'leader':   '👑',
        'deputy':   '🎖️',
        'coller':   '🎯',
        'builder':  '🔧',
        'electric': '⚡',
        'farmer':   '⛏️',
        'combater': '🗡️',
        'raider':   '💣',
        'ferm':     '🌾',
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
        'leader': 'Лидер', 'deputy': 'Зам', 'coller': 'Колер',
        'builder': 'Билдер', 'electric': 'Электрик', 'farmer': 'Фармер',
        'combater': 'Комбатер', 'raider': 'Рейдер', 'ferm': 'Фермер',
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


ACHIEVEMENTS = [
    {"id": 1, "icon": "🏆", "stat": "TOP 1", "name": "Facepunch Official",       "description": "Первое место на официальном сервере Facepunch EU. Доминировали весь вайп без потери главной базы.",                   "tier": "gold"},
    {"id": 2, "icon": "💀", "stat": "50+",   "name": "Successful Raids",         "description": "Более 50 успешных рейдов за последний сезон. Средняя длительность рейда — 18 минут.",                                  "tier": "default"},
    {"id": 3, "icon": "🏚️", "stat": "12×",   "name": "Wipe Dominators",          "description": "12 вайпов подряд с полным контролем карты к концу первого дня. Рекорд среди RU кланов.",                              "tier": "default"},
    {"id": 4, "icon": "⚡", "stat": "2:47",  "name": "Fastest Full Online Raid", "description": "Рекорд скорости рейда онлайн базы уровня T3 — 2 минуты 47 секунд от первого взрыва до лута.",                        "tier": "default"},
    {"id": 5, "icon": "🛡️", "stat": "0",     "name": "Bases Lost This Season",   "description": "Ноль потерянных баз за текущий сезон. Наши билдеры и электрики обеспечивают абсолютную защиту.",                     "tier": "default"},
    {"id": 6, "icon": "👑", "stat": "#1",    "name": "RU Clan Rankings",         "description": "Лучший русскоязычный клан по версии Rust Community Awards 2024. Голосование 14 000+ участников.",                     "tier": "gold"},
]

# ── API VIEWS ─────────────────────────────────────────────────

@api_view(['GET'])
def stats(request):
    qs = Server.objects.filter(is_active=True)
    online  = qs.filter(status='online').count()
    players = sum(s.players for s in qs.filter(status='online'))
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
    qs = Server.objects.filter(is_active=True)
    data = [
        {
            'id':          s.id,
            'name':        s.name,
            'type':        s.type,
            'status':      s.status,
            'players':     s.players,
            'max_players': s.max_players,
            'ping':        s.ping,
            'wipe_day':    s.wipe_day,
            'region':      s.region,
        }
        for s in qs
    ]
    return Response(data)


@api_view(['GET'])
def achievements(request):
    return Response(ACHIEVEMENTS)


@api_view(['GET'])
def videos(request):
    qs = Video.objects.filter(is_active=True)
    data = [
        {
            'id':            v.id,
            'title':         v.title,
            'category':      v.category,
            'duration':      v.duration,
            'views':         v.views,
            'date':          v.date,
            'url':           v.url,
            'thumbnail_url': v.thumbnail_url,
        }
        for v in qs
    ]
    return Response(data)


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

    # Получаем Steam-ник и аватар (если указан URL)
    steam_name = ''
    avatar_url = ''
    if steam_url:
        steam_data = fetch_steam_data(steam_url)
        steam_name = steam_data['name']
        avatar_url = steam_data['avatar_url']

    valid_roles = {'leader', 'deputy', 'coller', 'builder', 'electric', 'farmer', 'combater', 'raider', 'ferm'}
    if role not in valid_roles:
        role = 'farmer'

    user = User.objects.create_user(username=username, email=email, password=password)
    UserProfile.objects.create(user=user, steam_name=steam_name, steam_url=steam_url,
                               avatar_url=avatar_url, role=role, hours=hours)
    token, _ = Token.objects.get_or_create(user=user)
    send_register_webhook(username, steam_name, role, hours)
    return Response(
        {"ok": True, "message": "Аккаунт создан!", "token": token.key,
         "username": user.username, "steam_name": steam_name, "avatar_url": avatar_url},
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


@api_view(['GET', 'PATCH'])
def profile_view(request):
    """GET — возвращает профиль текущего пользователя.
    PATCH — обновляет steam_url / role / hours, перезагружает аватар из Steam."""
    auth_header = request.META.get('HTTP_AUTHORIZATION', '')
    if not auth_header.startswith('Token '):
        return Response({'ok': False, 'error': 'Требуется авторизация'}, status=401)
    token_key = auth_header[6:].strip()
    try:
        token_obj = Token.objects.select_related('user').get(key=token_key)
        user = token_obj.user
    except Token.DoesNotExist:
        return Response({'ok': False, 'error': 'Неверный токен'}, status=401)

    profile, _ = UserProfile.objects.get_or_create(user=user)

    if request.method == 'GET':
        return Response({
            'ok':           True,
            'username':     user.username,
            'email':        user.email,
            'display_name': profile.display_name,
            'steam_name':   profile.steam_name,
            'steam_url':    profile.steam_url,
            'avatar_url':   profile.avatar_url,
            'role':         profile.role,
            'hours':        profile.hours,
            'discord_tag':  profile.discord_tag,
            'region':       profile.region,
            'bio':          profile.bio,
            'date_joined':  user.date_joined.strftime('%d.%m.%Y'),
        })

    # PATCH
    steam_url    = request.data.get('steam_url',    profile.steam_url    or '').strip()
    role         = request.data.get('role',         profile.role)
    region       = request.data.get('region',       profile.region)
    display_name = request.data.get('display_name', profile.display_name or '').strip()[:64]
    discord_tag  = request.data.get('discord_tag',  profile.discord_tag  or '').strip()[:64]
    bio          = request.data.get('bio',          profile.bio          or '').strip()[:300]

    try:
        hours = int(request.data.get('hours', profile.hours) or 0)
    except (ValueError, TypeError):
        hours = profile.hours

    valid_roles   = {'leader', 'deputy', 'coller', 'builder', 'electric', 'farmer', 'combater', 'raider', 'ferm'}
    valid_regions = {'EU', 'RU', 'NA', 'ASIA'}
    if role   not in valid_roles:   role   = profile.role
    if region not in valid_regions: region = profile.region

    steam_name = profile.steam_name
    avatar_url = profile.avatar_url

    if steam_url != profile.steam_url:
        if steam_url:
            data       = fetch_steam_data(steam_url)
            steam_name = data['name']
            avatar_url = data['avatar_url']
        else:
            steam_name = ''
            avatar_url = ''

    profile.steam_url    = steam_url
    profile.steam_name   = steam_name
    profile.avatar_url   = avatar_url
    profile.role         = role
    profile.hours        = hours
    profile.display_name = display_name
    profile.discord_tag  = discord_tag
    profile.region       = region
    profile.bio          = bio
    profile.save()

    return Response({
        'ok':           True,
        'steam_name':   steam_name,
        'avatar_url':   avatar_url,
        'display_name': display_name,
        'role':         role,
        'hours':        hours,
        'discord_tag':  discord_tag,
        'region':       region,
        'bio':          bio,
    })


@api_view(['POST'])
def change_password(request):
    """Смена пароля по токену."""
    auth_header = request.META.get('HTTP_AUTHORIZATION', '')
    if not auth_header.startswith('Token '):
        return Response({'ok': False, 'error': 'Требуется авторизация'}, status=401)
    token_key = auth_header[6:].strip()
    try:
        token_obj = Token.objects.select_related('user').get(key=token_key)
        user = token_obj.user
    except Token.DoesNotExist:
        return Response({'ok': False, 'error': 'Неверный токен'}, status=401)

    old_pw = request.data.get('old_password', '')
    new_pw = request.data.get('new_password', '')

    if not user.check_password(old_pw):
        return Response({'ok': False, 'error': 'Неверный текущий пароль'}, status=400)
    if len(new_pw) < 8:
        return Response({'ok': False, 'error': 'Новый пароль — минимум 8 символов'}, status=400)

    user.set_password(new_pw)
    user.save()
    token_obj.delete()
    new_token, _ = Token.objects.get_or_create(user=user)
    return Response({'ok': True, 'token': new_token.key})


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


# ─────────────────────────────────────────────────────────
# Rust+ бот — веб-интерфейс настройки и статистики
# ─────────────────────────────────────────────────────────

from django.shortcuts import render
from django.utils import timezone as djtz
from .models import Player, Death


def _fmt_time(seconds):
    """Форматирует секунды в читаемый вид (используется в шаблонах)."""
    seconds = int(seconds)
    if seconds < 60:
        return f'{seconds}с'
    elif seconds < 3600:
        return f'{seconds // 60}м {seconds % 60}с'
    else:
        return f'{seconds // 3600}ч {(seconds % 3600) // 60}м'


def stats_view(request):
    """Публичная страница статистики игроков. URL: /stats/"""
    players_qs = Player.objects.all().order_by('-total_online_seconds')
    players_data = []

    for p in players_qs:
        deaths_count = Death.objects.filter(player=p).count()
        last_death   = Death.objects.filter(player=p).order_by('-timestamp').first()
        players_data.append({
            'player':       p,
            'deaths_count': deaths_count,
            'last_death':   last_death,
            'fmt_online':   _fmt_time(p.total_online_seconds),
            'fmt_city':     _fmt_time(p.total_city_seconds),
            'fmt_afk':      _fmt_time(p.total_afk_seconds),
        })

    return render(request, 'stats.html', {'players': players_data})


@api_view(['GET'])
def player_stats(request):
    """JSON API статистики игроков для фронтенда. URL: /api/player-stats/"""
    players_qs = Player.objects.all().order_by('-total_online_seconds')
    data = []

    for p in players_qs:
        deaths_count = Death.objects.filter(player=p).count()
        last_death   = Death.objects.filter(player=p).order_by('-timestamp').first()
        data.append({
            'steam_id':             p.steam_id,
            'name':                 p.name,
            'is_online':            p.is_online,
            'total_online_seconds': p.total_online_seconds,
            'total_city_seconds':   p.total_city_seconds,
            'total_afk_seconds':    p.total_afk_seconds,
            'deaths_count':         deaths_count,
            'last_death_grid':      last_death.grid_square if last_death else None,
            'last_seen':            p.last_seen.isoformat() if p.last_seen else None,
            'fmt_online':           _fmt_time(p.total_online_seconds),
            'fmt_city':             _fmt_time(p.total_city_seconds),
            'fmt_afk':              _fmt_time(p.total_afk_seconds),
        })

    return Response(data)
