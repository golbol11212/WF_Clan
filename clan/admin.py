from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from .models import Application, Member, WipePost, UserProfile
from .views import send_wipe_webhook, send_roster_webhook

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


# ── Заявки ───────────────────────────────────────────────────

@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display    = ['steam_name', 'discord_tag', 'role', 'region', 'hours', 'created_at']
    list_filter     = ['role', 'region']
    search_fields   = ['steam_name', 'discord_tag']
    readonly_fields = ['steam_name', 'discord_tag', 'hours', 'region', 'role', 'reason', 'created_at']
