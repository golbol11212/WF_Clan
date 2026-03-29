from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from .models import Application, Member, WipePost, UserProfile, Server, Video, BotConfig, CityZone, Player, Death
from .views import send_wipe_webhook, send_roster_webhook, fetch_video_meta

admin.site.unregister(User)

# ── Профиль юзера (инлайн внутри User) ───────────────────────

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name = 'Профиль (Steam / Роль)'
    fields = ('steam_name', 'steam_url', 'role', 'hours')
    readonly_fields = ('steam_name',)
    extra = 0


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    search_fields = ['username', 'email']
    list_display  = ['username', 'email', 'get_steam_name', 'get_role', 'get_hours', 'is_staff', 'date_joined']
    inlines       = [UserProfileInline]

    def get_steam_name(self, obj):
        p = getattr(obj, 'profile', None)
        return p.steam_name if p and p.steam_name else '—'
    get_steam_name.short_description = 'Steam ник'

    def get_role(self, obj):
        p = getattr(obj, 'profile', None)
        return p.get_role_display() if p else '—'
    get_role.short_description = 'Роль'

    def get_hours(self, obj):
        p = getattr(obj, 'profile', None)
        return p.hours if p else 0
    get_hours.short_description = 'Часов'


# ── Состав клана ──────────────────────────────────────────────

@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display   = ['display_name', 'get_steam', 'rank', 'specialization', 'region', 'hours', 'is_active', 'order']
    list_editable  = ['rank', 'specialization', 'is_active', 'order']
    list_filter    = ['rank', 'specialization', 'region', 'is_active']
    search_fields  = ['nickname', 'user__username', 'discord_tag']
    ordering       = ['order', 'nickname']
    autocomplete_fields = ['user']
    fieldsets = (
        (None, {
            'fields': ('user', 'nickname', 'rank', 'specialization', 'region', 'hours', 'is_active', 'order'),
            'description': (
                '⚡ Выбери игрока из списка — ник Steam, специализация и часы подтянутся автоматически. '
                'Поле "Никнейм" можно оставить пустым (будет использован Steam-ник).'
            ),
        }),
        ('Доп. информация', {
            'fields': ('discord_tag', 'avatar_url', 'join_date'),
            'classes': ('collapse',),
        }),
    )

    def display_name(self, obj):
        return obj.display_name()
    display_name.short_description = 'Отображаемый ник'

    def get_steam(self, obj):
        if obj.user:
            p = getattr(obj.user, 'profile', None)
            return p.steam_name if p and p.steam_name else '—'
        return '—'
    get_steam.short_description = 'Steam'

    def save_model(self, request, obj, form, change):
        if obj.user:
            profile = getattr(obj.user, 'profile', None)
            if not obj.nickname:
                obj.nickname = (profile.steam_name if profile and profile.steam_name else obj.user.username)
            if obj.hours == 0 and profile and profile.hours:
                obj.hours = profile.hours
            if obj.specialization == 'any' and profile and profile.role != 'any':
                obj.specialization = profile.role
        super().save_model(request, obj, form, change)
        send_roster_webhook()

    class Media:
        js = ('clan/admin_member.js',)


# ── Вайп ─────────────────────────────────────────────────────

@admin.register(WipePost)
class WipePostAdmin(admin.ModelAdmin):
    list_display      = ['title', 'server_name', 'wipe_date', 'is_active', 'created_at']
    list_editable     = ['is_active']
    list_filter       = ['is_active']
    search_fields     = ['title', 'server_name']
    filter_horizontal = ['squad']
    fieldsets = (
        (None, {
            'fields': ('title', 'server_name', 'connect', 'wipe_date', 'raid_plan', 'is_active'),
        }),
        ('Состав на вайп', {
            'fields': ('squad',),
        }),
        ('Доп. информация', {
            'fields': ('description',),
            'classes': ('collapse',),
        }),
    )

    def save_model(self, request, obj, form, change):
        # Запоминаем старый message_id до сохранения
        old_message_id = obj.discord_message_id if change else ''
        super().save_model(request, obj, form, change)
        # Удаляем старое сообщение и постим новое, сохраняем новый ID
        new_message_id = send_wipe_webhook(obj, old_message_id)
        if new_message_id:
            WipePost.objects.filter(pk=obj.pk).update(discord_message_id=new_message_id)


# ── Серверы ──────────────────────────────────────────────────

@admin.register(Server)
class ServerAdmin(admin.ModelAdmin):
    list_display  = ['name', 'type', 'status', 'players', 'max_players', 'ping', 'wipe_day', 'region', 'is_active', 'order']
    list_editable = ['status', 'players', 'ping', 'is_active', 'order']
    list_filter   = ['type', 'status', 'is_active']
    search_fields = ['name', 'region']
    ordering      = ['order', 'name']
    fieldsets = (
        (None, {
            'fields': ('name', 'type', 'status', 'is_active', 'order'),
        }),
        ('Статистика', {
            'fields': ('players', 'max_players', 'ping', 'wipe_day', 'region'),
        }),
    )


# ── Видео ─────────────────────────────────────────────────────

@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    list_display  = ['title', 'category', 'duration', 'views', 'date', 'is_active', 'order']
    list_editable = ['category', 'is_active', 'order']
    list_filter   = ['category', 'is_active']
    search_fields = ['title']
    ordering      = ['order', '-id']
    actions       = ['refresh_meta']
    fieldsets = (
        (None, {
            'fields': ('url', 'title', 'category', 'is_active', 'order'),
            'description': (
                '⚡ Вставь ссылку на YouTube/TikTok и сохрани — название подтянется автоматически. '
                'Для просмотров, длительности и даты нужен <b>YOUTUBE_API_KEY</b> в settings.py.'
            ),
        }),
        ('Мета (заполняется автоматически)', {
            'fields': ('thumbnail_url', 'duration', 'views', 'date'),
        }),
    )

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        form.base_fields['title'].required = False
        return form

    def save_model(self, request, obj, form, change):
        should_fetch = obj.url and (
            'url' in form.changed_data   # URL только что изменился
            or not obj.title             # нет названия
            or not obj.duration          # нет длительности
        )
        if should_fetch:
            meta = fetch_video_meta(obj.url)
            if meta['title']:
                obj.title = meta['title']
            if meta['duration']:
                obj.duration = meta['duration']
            if meta['views']:
                obj.views = meta['views']
            if meta['date']:
                obj.date = meta['date']
            if meta['thumbnail_url'] and not obj.thumbnail_url:
                obj.thumbnail_url = meta['thumbnail_url']
            if meta['title']:
                self.message_user(request, f'✅ Метаданные подтянуты: {meta["title"][:80]}')
            elif not obj.title:
                obj.title = obj.url  # fallback если fetch не сработал
        super().save_model(request, obj, form, change)

    @admin.action(description='🔄 Обновить метаданные из ссылки')
    def refresh_meta(self, request, queryset):
        updated = 0
        for obj in queryset:
            if not obj.url:
                continue
            meta = fetch_video_meta(obj.url)
            changed = False
            for field in ('title', 'duration', 'views', 'date', 'thumbnail_url'):
                if meta[field]:
                    setattr(obj, field, meta[field])
                    changed = True
            if changed:
                obj.save()
                updated += 1
        self.message_user(request, f'Обновлено {updated} видео.')


# ── Заявки ───────────────────────────────────────────────────

@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display    = ['steam_name', 'discord_tag', 'role', 'region', 'hours', 'created_at']
    list_filter     = ['role', 'region']
    search_fields   = ['steam_name', 'discord_tag']
    readonly_fields = ['steam_name', 'discord_tag', 'hours', 'region', 'role', 'reason', 'created_at']


# ── Rust+ бот ─────────────────────────────────────────────

@admin.register(BotConfig)
class BotConfigAdmin(admin.ModelAdmin):
    """Настройки подключения бота. Можно создать несколько для разных серверов."""
    list_display  = ('name', 'ip', 'port', 'steam_id', 'is_active', 'updated_at')
    list_editable = ('is_active',)
    fieldsets = (
        ('Название', {
            'fields': ('name',),
        }),
        ('Подключение к серверу', {
            'fields': ('ip', 'port', 'steam_id', 'player_token'),
        }),
        ('Статус', {
            'fields': ('is_active',),
        }),
    )


@admin.register(CityZone)
class CityZoneAdmin(admin.ModelAdmin):
    """Зона City на карте сервера."""
    list_display = ('name', 'server', 'x_min', 'x_max', 'y_min', 'y_max')


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    """Игроки, отслеживаемые ботом."""
    list_display  = ('name', 'steam_id', 'is_online', 'fmt_online', 'fmt_city', 'fmt_afk', 'last_seen')
    list_filter   = ('is_online',)
    search_fields = ('name', 'steam_id')
    readonly_fields = (
        'last_seen', 'session_start', 'is_online',
        'total_online_seconds', 'total_city_seconds', 'total_afk_seconds',
        'last_x', 'last_y', 'last_move_time',
    )

    def get_readonly_fields(self, request, obj=None):
        # При редактировании существующего игрока steam_id тоже readonly
        if obj:
            return self.readonly_fields + ('steam_id',)
        return self.readonly_fields

    @admin.display(description='Онлайн')
    def fmt_online(self, obj):
        return _fmt_time_admin(obj.total_online_seconds)

    @admin.display(description='Время в City')
    def fmt_city(self, obj):
        return _fmt_time_admin(obj.total_city_seconds)

    @admin.display(description='АФК')
    def fmt_afk(self, obj):
        return _fmt_time_admin(obj.total_afk_seconds)


@admin.register(Death)
class DeathAdmin(admin.ModelAdmin):
    """Смерти игроков."""
    list_display    = ('player', 'timestamp', 'grid_square', 'x', 'y', 'map_size')
    list_filter     = ('player',)
    date_hierarchy  = 'timestamp'
    readonly_fields = ('player', 'timestamp', 'x', 'y', 'grid_square', 'map_size')


def _fmt_time_admin(seconds):
    """Вспомогательная функция форматирования времени для Admin."""
    if seconds < 60:
        return f'{seconds}с'
    elif seconds < 3600:
        return f'{seconds // 60}м'
    else:
        return f'{seconds // 3600}ч {(seconds % 3600) // 60}м'
