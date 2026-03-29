"""
Миграция: добавляет модели BotConfig, CityZone, Player, Death
для Rust+ бота.
"""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        # Предыдущая миграция в этом приложении
        ('clan', '0011_video_thumbnail'),
    ]

    operations = [

        # ── BotConfig ────────────────────────────────────────
        migrations.CreateModel(
            name='BotConfig',
            fields=[
                ('id',           models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ip',           models.CharField(max_length=64, verbose_name='IP адрес сервера')),
                ('port',         models.IntegerField(default=28017, verbose_name='Порт сервера')),
                ('steam_id',     models.BigIntegerField(verbose_name='Steam ID (64-bit)')),
                ('player_token', models.BigIntegerField(verbose_name='Rust+ токен')),
                ('is_active',    models.BooleanField(default=False, verbose_name='Бот включён')),
                ('updated_at',   models.DateTimeField(auto_now=True, verbose_name='Обновлено')),
            ],
            options={
                'verbose_name':        'Настройки бота',
                'verbose_name_plural': 'Настройки бота',
            },
        ),

        # ── CityZone ─────────────────────────────────────────
        migrations.CreateModel(
            name='CityZone',
            fields=[
                ('id',    models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name',  models.CharField(default='City', max_length=64, verbose_name='Название зоны')),
                ('x_min', models.FloatField(default=0, verbose_name='X минимум')),
                ('x_max', models.FloatField(default=0, verbose_name='X максимум')),
                ('y_min', models.FloatField(default=0, verbose_name='Y минимум')),
                ('y_max', models.FloatField(default=0, verbose_name='Y максимум')),
            ],
            options={
                'verbose_name':        'Зона City',
                'verbose_name_plural': 'Зоны City',
            },
        ),

        # ── Player ───────────────────────────────────────────
        migrations.CreateModel(
            name='Player',
            fields=[
                ('id',                   models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('steam_id',             models.BigIntegerField(unique=True, verbose_name='Steam ID')),
                ('name',                 models.CharField(max_length=64, verbose_name='Имя игрока')),
                ('last_seen',            models.DateTimeField(blank=True, null=True, verbose_name='Последний онлайн')),
                ('session_start',        models.DateTimeField(blank=True, null=True, verbose_name='Начало текущей сессии')),
                ('total_online_seconds', models.IntegerField(default=0, verbose_name='Всего онлайн (сек)')),
                ('total_city_seconds',   models.IntegerField(default=0, verbose_name='Всего в City (сек)')),
                ('total_afk_seconds',    models.IntegerField(default=0, verbose_name='Всего АФК (сек)')),
                ('last_x',               models.FloatField(blank=True, null=True, verbose_name='Последняя позиция X')),
                ('last_y',               models.FloatField(blank=True, null=True, verbose_name='Последняя позиция Y')),
                ('last_move_time',       models.DateTimeField(blank=True, null=True, verbose_name='Последнее движение')),
                ('is_online',            models.BooleanField(default=False, verbose_name='Онлайн')),
            ],
            options={
                'verbose_name':        'Игрок (бот)',
                'verbose_name_plural': 'Игроки (бот)',
                'ordering':            ['-total_online_seconds'],
            },
        ),

        # ── Death ─────────────────────────────────────────────
        migrations.CreateModel(
            name='Death',
            fields=[
                ('id',          models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('player',      models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='deaths', to='clan.player', verbose_name='Игрок')),
                ('timestamp',   models.DateTimeField(auto_now_add=True, verbose_name='Время смерти')),
                ('x',           models.FloatField(verbose_name='Координата X')),
                ('y',           models.FloatField(verbose_name='Координата Y')),
                ('grid_square', models.CharField(max_length=8, verbose_name='Квадрат карты')),
                ('map_size',    models.IntegerField(verbose_name='Размер карты')),
            ],
            options={
                'verbose_name':        'Смерть',
                'verbose_name_plural': 'Смерти',
                'ordering':            ['-timestamp'],
            },
        ),
    ]
