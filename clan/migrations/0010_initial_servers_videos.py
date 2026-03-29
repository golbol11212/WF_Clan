from django.db import migrations


def populate_servers(apps, schema_editor):
    Server = apps.get_model('clan', 'Server')
    rows = [
        dict(name='WF | EU MAIN — VANILLA x1',      type='vanilla',  status='online',  players=186, max_players=200, ping=18,   wipe_day='ЧТ 20:00',       region='EU-WEST', order=1),
        dict(name='WF | EU MODDED — x2 GATHER',     type='modded',   status='online',  players=78,  max_players=150, ping=22,   wipe_day='ПТ 19:00',       region='EU-WEST', order=2),
        dict(name='WF | TRAINING — AIM & ELECTRIC',  type='training', status='online',  players=20,  max_players=50,  ping=34,   wipe_day='—',              region='EU-WEST', order=3),
        dict(name='WF | EU MAIN 2 — VANILLA x1',    type='vanilla',  status='offline', players=0,   max_players=200, ping=None, wipe_day='СЛЕДУЮЩИЙ ВАЙП', region='EU-EAST', order=4),
    ]
    for r in rows:
        Server.objects.create(**r)


def populate_videos(apps, schema_editor):
    Video = apps.get_model('clan', 'Video')
    rows = [
        dict(title='РЕЙД БАЗЫ Т4 — ONLINE RAID 2025',        category='raid',  duration='18:34', views='847K', date='12 ЯНВ 2025', order=1),
        dict(title='COLLER vs 10 PLAYERS — NO CLIP',          category='pvp',   duration='12:08', views='520K', date='5 ФЕВ 2025',  order=2),
        dict(title='МЕГА БАЗА — BUNKER + ЭЛЕКТРИКА 2025',     category='build', duration='28:45', views='312K', date='20 ЯНВ 2025', order=3),
        dict(title='ГАЙД: ЭЛЕКТРИКА ДЛЯ НОВИЧКОВ 2025',      category='guide', duration='22:17', views='680K', date='3 МАР 2025',  order=4),
        dict(title='САМЫЙ БЫСТРЫЙ РЕЙД — 2:47 WORLD RECORD', category='raid',  duration='35:02', views='1.1M', date='15 МАЙ 2024', order=5),
        dict(title='WF COLLERS — WIPE DAY PVP MONTAGE',       category='pvp',   duration='09:51', views='290K', date='28 ФЕВ 2025', order=6),
    ]
    for r in rows:
        Video.objects.create(**r)


class Migration(migrations.Migration):

    dependencies = [
        ('clan', '0009_add_server_video'),
    ]

    operations = [
        migrations.RunPython(populate_servers, migrations.RunPython.noop),
        migrations.RunPython(populate_videos,  migrations.RunPython.noop),
    ]
