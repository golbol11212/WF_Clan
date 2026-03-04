from django.contrib import admin
from .models import Application


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display  = ['steam_name', 'discord_tag', 'role', 'region', 'hours', 'created_at']
    list_filter   = ['role', 'region']
    search_fields = ['steam_name', 'discord_tag']
    readonly_fields = ['created_at']
