import urllib.request
import urllib.error
import json
from datetime import datetime, timezone

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .models import Application
from .serializers import ApplicationSerializer


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
    username = request.data.get('username', '').strip()
    email    = request.data.get('email', '').strip()
    password = request.data.get('password', '')

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

    user = User.objects.create_user(username=username, email=email, password=password)
    token, _ = Token.objects.get_or_create(user=user)
    return Response(
        {"ok": True, "message": "Аккаунт создан!", "token": token.key, "username": user.username},
        status=status.HTTP_201_CREATED,
    )


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
