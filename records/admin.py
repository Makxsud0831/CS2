from django.contrib import admin
from .models import PlayerRecord, RecordHistory, MapCompletion


@admin.register(PlayerRecord)
class PlayerRecordAdmin(admin.ModelAdmin):
    list_display = ['user', 'map', 'style', 'time_display', 'jumps', 'sync', 'set_at']
    list_filter = ['style', 'map__map_type']
    search_fields = ['user__username', 'map__name']
    ordering = ['map', 'style', 'time_ms']
    readonly_fields = ['set_at']


@admin.register(RecordHistory)
class RecordHistoryAdmin(admin.ModelAdmin):
    list_display = ['user', 'map', 'style', 'time_ms', 'improvement_ms', 'set_at']
    list_filter = ['style']
    search_fields = ['user__username', 'map__name']
    ordering = ['-set_at']


@admin.register(MapCompletion)
class MapCompletionAdmin(admin.ModelAdmin):
    list_display = ['user', 'map', 'style', 'count', 'last_played']
    search_fields = ['user__username', 'map__name']
