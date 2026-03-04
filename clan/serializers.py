from rest_framework import serializers
from .models import Application


class ApplicationSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Application
        fields = ['id', 'steam_name', 'discord_tag', 'hours', 'region', 'role', 'reason', 'created_at']
        read_only_fields = ['id', 'created_at']
