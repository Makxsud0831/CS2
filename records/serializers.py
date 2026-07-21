from rest_framework import serializers
from .models import PlayerRecord, RecordHistory, MapCompletion


class PlayerRecordSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    steam_id = serializers.SerializerMethodField()
    map_name = serializers.CharField(source='map.name', read_only=True)
    time_display = serializers.CharField(read_only=True)
    rank = serializers.SerializerMethodField()

    class Meta:
        model = PlayerRecord
        fields = [
            'id', 'username', 'steam_id', 'map_name', 'style',
            'time_ms', 'time_display', 'jumps', 'strafes', 'sync',
            'pre_speed', 'max_speed', 'set_at', 'rank',
        ]

    def get_steam_id(self, obj):
        return obj.user.get_steam_id()

    def get_rank(self, obj):
        return (
            PlayerRecord.objects
            .filter(map=obj.map, style=obj.style, time_ms__lte=obj.time_ms)
            .count()
        )


class RecordHistorySerializer(serializers.ModelSerializer):
    time_display = serializers.SerializerMethodField()

    class Meta:
        model = RecordHistory
        fields = ['time_ms', 'time_display', 'jumps', 'set_at', 'improvement_ms']

    def get_time_display(self, obj):
        total = obj.time_ms / 1000.0
        minutes = int(total // 60)
        seconds = total % 60
        if minutes:
            return f"{minutes}:{seconds:06.3f}"
        return f"{seconds:.3f}"


class MapCompletionSerializer(serializers.ModelSerializer):
    map_name = serializers.CharField(source='map.name', read_only=True)
    map_type = serializers.CharField(source='map.map_type', read_only=True)

    class Meta:
        model = MapCompletion
        fields = ['map_name', 'map_type', 'style', 'count', 'last_played']
