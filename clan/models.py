from django.db import models
from django.contrib.auth.models import User


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
        ('raider',  'Raider'),
        ('builder', 'Builder / Electrician'),
        ('pvp',     'PVP / Coller'),
        ('farmer',  'Farmer / Support'),
        ('any',     'Any'),
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
    join_date    = models.DateField('Дата вступления', null=True, blank=True)
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
        ('raider',  'Raider'),
        ('builder', 'Builder / Electrician'),
        ('pvp',     'PVP / Coller'),
        ('farmer',  'Farmer / Support'),
        ('any',     'Any'),
    ]

    user       = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    steam_name = models.CharField('Steam-ник',     max_length=64,  blank=True, default='')
    steam_url  = models.CharField('Steam профиль', max_length=256, blank=True, default='')
    role       = models.CharField('Роль',          max_length=16,  choices=ROLE_CHOICES, default='any')
    hours      = models.PositiveIntegerField('Часов в Rust', default=0)

    class Meta:
        verbose_name        = 'Профиль'
        verbose_name_plural = 'Профили игроков'

    def __str__(self):
        return f'{self.user.username} — {self.steam_name or "без Steam"}'


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


class Application(models.Model):
    """Заявки на вступление в клан (отправляются через форму на сайте)."""

    REGION_CHOICES = [
        ('EU', 'EU'),
        ('RU', 'RU'),
        ('NA', 'NA'),
        ('ASIA', 'ASIA'),
    ]
    ROLE_CHOICES = [
        ('raider', 'Raider'),
        ('builder', 'Builder / Electrician'),
        ('pvp', 'PVP / Coller'),
        ('farmer', 'Farmer / Support'),
        ('any', 'Any'),
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
