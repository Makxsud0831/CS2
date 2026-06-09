from django.contrib import admin
from .models import GameServer, ServerConfig, ServerMap, MapConfig


@admin.register(GameServer)
class GameServerAdmin(admin.ModelAdmin):
    list_display = ['name', 'ip', 'port', 'is_online', 'region']


@admin.register(ServerConfig)
class ServerConfigAdmin(admin.ModelAdmin):
    list_display = ['server', 'gamemode', 'max_players', 'tickrate']


@admin.register(ServerMap)
class ServerMapAdmin(admin.ModelAdmin):
    list_display = ['name', 'server', 'map_type', 'is_active', 'is_current']


@admin.register(MapConfig)
class MapConfigAdmin(admin.ModelAdmin):
    list_display = ['server_map', 'bhop_enabled', 'auto_bhop', 'max_velocity']
