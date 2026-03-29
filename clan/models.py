from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Member(models.Model):
    """Состав клана — управляется через Admin."""

    RANK_CHOICES = [
        ('leader',    'Leader'),
        ('co-leader', 'Co-Leader'),
        ('veteran',   'Veteran'),
        ('member',    'Member'),
        ('recruit',   'Recruit'),
    ]
    SPEC_CHOICES = [
        ('leader',   'Лидер'),
        ('deputy',   'Зам'),
        ('coller',   'Колер'),
        ('builder',  'Билдер'),
        ('electric', 'Электрик'),
        ('farmer',   'Фармер'),
        ('combater', 'Комбатер'),
        ('raider',   'Рейдер'),
        ('ferm',     'Фермер'),
    ]
    REGION_CHOICES = [
        ('EU',   'EU'),
        ('RU',   'RU'),
        ('NA',   'NA'),
        ('ASIA', 'ASIA'),
    ]

    user         = models.OneToOneField(User, verbose_name='Игрок (аккаунт)', on_delete=models.CASCADE, null=True, blank=True, related_name='member_profile')
    nickname     = models.CharField('Никнейм (отображаемый)', max_length=64, blank=True, default='')
    rank         = models.CharField('Звание',        max_length=16,  choices=RANK_CHOICES, default='member')
    specialization = models.CharField('Специализация', max_length=16, choices=SPEC_CHOICES, default='any')
    region       = models.CharField('Регион',        max_length=8,   choices=REGION_CHOICES, default='EU')
    hours        = models.PositiveIntegerField('Часов в Rust', default=0)
    avatar_url   = models.URLField('Ссылка на аватар', blank=True, default='')
    discord_tag  = models.CharField('Discord',       max_length=64,  blank=True, default='')
    join_date    = models.DateField('Дата вступления', default=timezone.localdate, blank=True)
    is_active    = models.BooleanField('Показывать на сайте', default=True)
    order        = models.PositiveSmallIntegerField('Порядок', default=100)

    class Meta:
        verbose_name        = 'Участник'
        verbose_name_plural = 'Состав клана'
        ordering            = ['order', 'nickname']

    def display_name(self):
        if self.nickname:
            return self.nickname
        if self.user:
            steam = getattr(self.user, 'profile', None)
            if steam and steam.steam_name:
                return steam.steam_name
            return self.user.username
        return '—'

    def __str__(self):
        return f'{self.display_name()} [{self.get_rank_display()}]'


class UserProfile(models.Model):
    """Профиль пользователя сайта — Steam ник и роль."""

    ROLE_CHOICES = [
        ('leader',   'Лидер'),
        ('deputy',   'Зам'),
        ('coller',   'Колер'),
        ('builder',  'Билдер'),
        ('electric', 'Электрик'),
        ('farmer',   'Фармер'),
        ('combater', 'Комбатер'),
        ('raider',   'Рейдер'),
        ('ferm',     'Фермер'),
    ]

    REGION_CHOICES = [
        ('EU',   'EU'),
        ('RU',   'RU'),
        ('NA',   'NA'),
        ('ASIA', 'ASIA'),
    ]

    user         = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    display_name = models.CharField('Отображаемое имя', max_length=64,  blank=True, default='')
    steam_name   = models.CharField('Steam-ник',        max_length=64,  blank=True, default='')
    steam_url    = models.CharField('Steam профиль',    max_length=256, blank=True, default='')
    avatar_url   = models.URLField('Аватар Steam',      max_length=512, blank=True, default='')
    role         = models.CharField('Роль',             max_length=16,  choices=ROLE_CHOICES, default='any')
    hours        = models.PositiveIntegerField('Часов в Rust', default=0)
    discord_tag  = models.CharField('Discord',          max_length=64,  blank=True, default='')
    region       = models.CharField('Регион',           max_length=8,   choices=REGION_CHOICES, default='EU')
    bio          = models.TextField('О себе',           max_length=300, blank=True, default='')

    class Meta:
        verbose_name        = 'Профиль'
        verbose_name_plural = 'Профили игроков'

    def __str__(self):
        return f'{self.user.username} — {self.steam_name or "без Steam"}'


class Server(models.Model):
    """Игровые серверы клана."""

    TYPE_CHOICES = [
        ('vanilla',  'Vanilla'),
        ('modded',   'Modded'),
        ('training', 'Training'),
    ]
    STATUS_CHOICES = [
        ('online',  'Online'),
        ('offline', 'Offline'),
    ]

    name        = models.CharField('Название',       max_length=128)
    type        = models.CharField('Тип',            max_length=16, choices=TYPE_CHOICES, default='vanilla')
    status      = models.CharField('Статус',         max_length=16, choices=STATUS_CHOICES, default='online')
    players     = models.PositiveIntegerField('Игроков онлайн', default=0)
    max_players = models.PositiveIntegerField('Макс. игроков',  default=200)
    ping        = models.PositiveIntegerField('Пинг (мс)',      null=True, blank=True)
    wipe_day    = models.CharField('День вайпа',    max_length=64, blank=True, default='')
    region      = models.CharField('Регион',        max_length=32, blank=True, default='')
    is_active   = models.BooleanField('Показывать', default=True)
    order       = models.PositiveSmallIntegerField('Порядок', default=100)

    class Meta:
        verbose_name        = 'Сервер'
        verbose_name_plural = 'Серверы'
        ordering            = ['order', 'name']

    def __str__(self):
        return self.name


class Video(models.Model):
    """Видео клана."""

    CATEGORY_CHOICES = [
        ('raid',  'Рейд'),
        ('pvp',   'PVP'),
        ('build', 'Строительство'),
        ('guide', 'Гайд'),
    ]

    title     = models.CharField('Заголовок',   max_length=256)
    category  = models.CharField('Категория',   max_length=16, choices=CATEGORY_CHOICES, default='raid')
    duration  = models.CharField('Длительность', max_length=16, blank=True, default='')
    views     = models.CharField('Просмотры',   max_length=16, blank=True, default='')
    date      = models.CharField('Дата',        max_length=32, blank=True, default='')
    url           = models.URLField('Ссылка на видео', blank=True, default='')
    thumbnail_url = models.URLField('Превью (автоматически)', blank=True, default='')
    is_active = models.BooleanField('Показывать', default=True)
    order     = models.PositiveSmallIntegerField('Порядок', default=100)

    class Meta:
        verbose_name        = 'Видео'
        verbose_name_plural = 'Видео'
        ordering            = ['order', '-id']

    def __str__(self):
        return self.title


class WipePost(models.Model):
    """Информация о вайпе — текущем и архивных."""

    title       = models.CharField('Заголовок',       max_length=128)
    server_name = models.CharField('Название сервера', max_length=128)
    connect     = models.CharField('Коннект (команда)', max_length=128,
                                   help_text='Пример: client.connect 185.0.0.1:28015')
    wipe_date   = models.DateTimeField('Дата вайпа')
    raid_plan   = models.CharField('Расписание рейдов', max_length=256, blank=True, default='',
                                   help_text='Пример: Первый рейд — 20:00 МСК / Ночной — 02:00')
    description = models.TextField('Доп. информация', blank=True, default='')
    squad       = models.ManyToManyField('Member', verbose_name='Состав', blank=True,
                                         related_name='wipe_posts')
    is_active          = models.BooleanField('Текущий вайп (закреплён)', default=False,
                                             help_text='Только один вайп может быть активным')
    discord_message_id = models.CharField(max_length=32, blank=True, default='')
    created_at         = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Вайп'
        verbose_name_plural = 'Вайпы'
        ordering            = ['-created_at']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        # Снимаем is_active у всех остальных при активации этого
        if self.is_active:
            WipePost.objects.exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)


class DiscordMessage(models.Model):
    """Хранит ID сообщений Discord для последующего удаления/редактирования."""
    key        = models.CharField(max_length=32, unique=True)
    message_id = models.CharField(max_length=32, blank=True, default='')

    class Meta:
        verbose_name        = 'Discord сообщение'
        verbose_name_plural = 'Discord сообщения'

    def __str__(self):
        return f'{self.key}: {self.message_id}'


# ─────────────────────────────────────────────────────────
# Rust+ бот — конфигурация, зоны, игроки и смерти
# ─────────────────────────────────────────────────────────

class BotConfig(models.Model):
    """Настройки подключения Rust+ бота. Можно создать несколько для разных серверов."""

    name         = models.CharField('Название', max_length=64, default='Main')
    ip           = models.CharField('IP адрес сервера', max_length=64)
    port         = models.IntegerField('Порт сервера', default=28017)
    steam_id     = models.BigIntegerField('Steam ID (64-bit)')
    player_token = models.BigIntegerField('Rust+ токен')
    is_active    = models.BooleanField('Бот включён', default=False)
    updated_at   = models.DateTimeField('Обновлено', auto_now=True)

    class Meta:
        verbose_name        = 'Настройки бота'
        verbose_name_plural = 'Настройки бота'

    def __str__(self):
        status = '✅' if self.is_active else '❌'
        return f'[{self.name}] {self.ip}:{self.port} {status}'


class CityZone(models.Model):
    """Зона 'City' на карте сервера. Своя для каждого сервера."""

    server = models.OneToOneField(
        BotConfig, on_delete=models.CASCADE,
        verbose_name='Сервер', null=True, blank=True, related_name='city_zone'
    )
    name  = models.CharField('Название зоны', max_length=64, default='City')
    x_min = models.FloatField('X минимум', default=0)
    x_max = models.FloatField('X максимум', default=0)
    y_min = models.FloatField('Y минимум', default=0)
    y_max = models.FloatField('Y максимум', default=0)

    class Meta:
        verbose_name        = 'Зона City'
        verbose_name_plural = 'Зоны City'

    def __str__(self):
        server_name = self.server.name if self.server else '—'
        return f'{self.name} [{server_name}] (X: {self.x_min}–{self.x_max}, Y: {self.y_min}–{self.y_max})'

    def contains(self, x, y):
        """Проверяет, попадают ли координаты в зону."""
        return self.x_min <= x <= self.x_max and self.y_min <= y <= self.y_max


class Player(models.Model):
    """Игрок из команды (тимейт), отслеживаемый ботом."""

    steam_id             = models.BigIntegerField('Steam ID', unique=True)
    name                 = models.CharField('Имя игрока', max_length=64)
    last_seen            = models.DateTimeField('Последний онлайн', null=True, blank=True)
    session_start        = models.DateTimeField('Начало текущей сессии', null=True, blank=True)
    total_online_seconds = models.IntegerField('Всего онлайн (сек)', default=0)
    total_city_seconds   = models.IntegerField('Всего в City (сек)', default=0)
    total_afk_seconds    = models.IntegerField('Всего АФК (сек)', default=0)
    last_x               = models.FloatField('Последняя позиция X', null=True, blank=True)
    last_y               = models.FloatField('Последняя позиция Y', null=True, blank=True)
    last_move_time       = models.DateTimeField('Последнее движение', null=True, blank=True)
    is_online            = models.BooleanField('Онлайн', default=False)

    class Meta:
        verbose_name        = 'Игрок (бот)'
        verbose_name_plural = 'Игроки (бот)'
        ordering            = ['-total_online_seconds']

    def __str__(self):
        status = '🟢' if self.is_online else '⚫'
        return f'{status} {self.name} [{self.steam_id}]'


class Death(models.Model):
    """Запись о смерти игрока."""

    player      = models.ForeignKey(Player, on_delete=models.CASCADE,
                                    related_name='deaths', verbose_name='Игрок')
    timestamp   = models.DateTimeField('Время смерти', auto_now_add=True)
    x           = models.FloatField('Координата X')
    y           = models.FloatField('Координата Y')
    grid_square = models.CharField('Квадрат карты', max_length=8)
    map_size    = models.IntegerField('Размер карты')

    class Meta:
        verbose_name        = 'Смерть'
        verbose_name_plural = 'Смерти'
        ordering            = ['-timestamp']

    def __str__(self):
        return f'{self.player.name} @ {self.grid_square} ({self.timestamp.strftime("%d.%m %H:%M")})'


# ─────────────────────────────────────────────────────────

class Application(models.Model):
    """Заявки на вступление в клан (отправляются через форму на сайте)."""

    REGION_CHOICES = [
        ('EU', 'EU'),
        ('RU', 'RU'),
        ('NA', 'NA'),
        ('ASIA', 'ASIA'),
    ]
    ROLE_CHOICES = [
        ('leader',   'Лидер'),
        ('deputy',   'Зам'),
        ('coller',   'Колер'),
        ('builder',  'Билдер'),
        ('electric', 'Электрик'),
        ('farmer',   'Фармер'),
        ('combater', 'Комбатер'),
        ('raider',   'Рейдер'),
        ('ferm',     'Фермер'),
    ]

    steam_name  = models.CharField('Steam-имя',  max_length=64)
    discord_tag = models.CharField('Discord',     max_length=64)
    hours       = models.PositiveIntegerField('Часов в Rust')
    region      = models.CharField('Регион',  max_length=8,  choices=REGION_CHOICES)
    role        = models.CharField('Роль',    max_length=16, choices=ROLE_CHOICES)
    reason      = models.TextField('Почему хочешь к нам')
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Заявка'
        verbose_name_plural = 'Заявки'
        ordering            = ['-created_at']

    def __str__(self):
        return f'{self.steam_name} ({self.discord_tag})'
