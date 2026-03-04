from django.db import models


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
