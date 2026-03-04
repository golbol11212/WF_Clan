from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional
import uvicorn

app = FastAPI(title="WF Clan API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── MODELS ────────────────────────────────────────────────────

class Server(BaseModel):
    id: int
    name: str
    type: str           # vanilla | modded | training
    status: str         # online | offline
    players: int
    max_players: int
    ping: Optional[int]
    wipe_day: str
    region: str

class Achievement(BaseModel):
    id: int
    icon: str
    stat: str
    name: str
    description: str
    tier: str           # gold | default

class Video(BaseModel):
    id: int
    title: str
    category: str       # raid | pvp | build | guide
    duration: str
    views: str
    date: str
    youtube_url: Optional[str] = None

class ClanStats(BaseModel):
    members: int
    win_rate: int
    years_active: int
    raids_won: int
    global_rank: str
    servers_online: int
    total_players: int

class Application(BaseModel):
    steam_name: str
    discord_tag: str
    hours: int
    region: str
    role: str
    reason: str

# ── DATA ──────────────────────────────────────────────────────

servers_db: List[Server] = [
    Server(id=1, name="WF | EU MAIN — VANILLA x1",     type="vanilla",  status="online",  players=186, max_players=200, ping=18,   wipe_day="ЧТ 20:00",        region="EU-WEST"),
    Server(id=2, name="WF | EU MODDED — x2 GATHER",    type="modded",   status="online",  players=78,  max_players=150, ping=22,   wipe_day="ПТ 19:00",        region="EU-WEST"),
    Server(id=3, name="WF | TRAINING — AIM & ELECTRIC", type="training", status="online",  players=20,  max_players=50,  ping=34,   wipe_day="—",               region="EU-WEST"),
    Server(id=4, name="WF | EU MAIN 2 — VANILLA x1",   type="vanilla",  status="offline", players=0,   max_players=200, ping=None, wipe_day="СЛЕДУЮЩИЙ ВАЙП", region="EU-EAST"),
]

achievements_db: List[Achievement] = [
    Achievement(id=1, icon="🏆", stat="TOP 1", name="Facepunch Official",      description="Первое место на официальном сервере Facepunch EU. Доминировали весь вайп без потери главной базы.",                              tier="gold"),
    Achievement(id=2, icon="💀", stat="50+",   name="Successful Raids",        description="Более 50 успешных рейдов за последний сезон. Средняя длительность рейда — 18 минут.",                                             tier="default"),
    Achievement(id=3, icon="🏚️", stat="12×",   name="Wipe Dominators",         description="12 вайпов подряд с полным контролем карты к концу первого дня. Рекорд среди RU кланов.",                                         tier="default"),
    Achievement(id=4, icon="⚡", stat="2:47",  name="Fastest Full Online Raid", description="Рекорд скорости рейда онлайн базы уровня T3 — 2 минуты 47 секунд от первого взрыва до лута.",                                   tier="default"),
    Achievement(id=5, icon="🛡️", stat="0",     name="Bases Lost This Season",   description="Ноль потерянных баз за текущий сезон. Наши билдеры и электрики обеспечивают абсолютную защиту.",                                tier="default"),
    Achievement(id=6, icon="👑", stat="#1",    name="RU Clan Rankings",         description="Лучший русскоязычный клан по версии Rust Community Awards 2024. Голосование 14,000+ участников.",                               tier="gold"),
]

videos_db: List[Video] = [
    Video(id=1, title="РЕЙД БАЗЫ Т4 — ONLINE RAID 2025",          category="raid",  duration="18:34", views="847K",  date="12 ЯНВ 2025"),
    Video(id=2, title="COLLER vs 10 PLAYERS — NO CLIP",            category="pvp",   duration="12:08", views="520K",  date="5 ФЕВ 2025"),
    Video(id=3, title="МЕГА БАЗА — BUNKER + ЭЛЕКТРИКА 2025",       category="build", duration="28:45", views="312K",  date="20 ЯНВ 2025"),
    Video(id=4, title="ГАЙД: ЭЛЕКТРИКА ДЛЯ НОВИЧКОВ 2025",        category="guide", duration="22:17", views="680K",  date="3 МАР 2025"),
    Video(id=5, title="САМЫЙ БЫСТРЫЙ РЕЙД — 2:47 WORLD RECORD",   category="raid",  duration="35:02", views="1.1M",  date="15 МАЙ 2024"),
    Video(id=6, title="WF COLLERS — WIPE DAY PVP MONTAGE",         category="pvp",   duration="09:51", views="290K",  date="28 ФЕВ 2025"),
]

applications_db: List[dict] = []

# ── API ROUTES ────────────────────────────────────────────────

@app.get("/api/stats", response_model=ClanStats)
def get_stats():
    online = sum(1 for s in servers_db if s.status == "online")
    players = sum(s.players for s in servers_db)
    return ClanStats(
        members=247,
        win_rate=89,
        years_active=4,
        raids_won=1200,
        global_rank="#03",
        servers_online=online,
        total_players=players,
    )

@app.get("/api/servers", response_model=List[Server])
def get_servers():
    return servers_db

@app.get("/api/achievements", response_model=List[Achievement])
def get_achievements():
    return achievements_db

@app.get("/api/videos", response_model=List[Video])
def get_videos():
    return videos_db

@app.post("/api/apply", status_code=201)
def submit_application(app_data: Application):
    record = app_data.model_dump()
    record["id"] = len(applications_db) + 1
    applications_db.append(record)
    return {"ok": True, "message": "Заявка принята. Мы свяжемся с вами в Discord.", "id": record["id"]}

# ── PAGES ─────────────────────────────────────────────────────

@app.get("/")
def serve_clan():
    return FileResponse("wf-clan.html")

@app.get("/hub")
def serve_hub():
    return FileResponse("wf-hub.html")

# ── ENTRY POINT ───────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
