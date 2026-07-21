from rest_framework import serializers
from .models import STPlayerRecord, STPlayerStats, PlayerRecord


class STRecordSerializer(serializers.ModelSerializer):
    time_ms = serializers.FloatField(read_only=True)
    time_display = serializers.CharField(read_only=True)

    class Meta:
        model = STPlayerRecord
        fields = [
            'SteamID', 'PlayerName', 'MapName', 'Style',
            'time_ms', 'time_display', 'TimesFinished', 'LastFinished',
        ]


class STPlayerStatsSerializer(serializers.ModelSerializer):
    class Meta:
        model = STPlayerStats
        fields = [
            'SteamID', 'PlayerName', 'GlobalPoints',
            'TimesConnected', 'LastConnected', 'HideStats',
        ]


class PlayerStatsSerializer(serializers.Serializer):
    """
    O'yinchi umumiy statistikasi — SharpTimer + Django records birlashtirilgan.
    """
    steam_id = serializers.CharField()
    steam_name = serializers.CharField()
    global_points = serializers.IntegerField()
    total_maps_completed = serializers.IntegerField()
    total_runs = serializers.IntegerField()
    rank = serializers.IntegerField()
    total_players = serializers.IntegerField()
    top_records = STRecordSerializer(many=True)


class MapLeaderboardEntrySerializer(serializers.Serializer):
    rank = serializers.IntegerField()
    steam_id = serializers.CharField()
    steam_name = serializers.CharField()
    time_display = serializers.CharField()
    time_ms = serializers.FloatField()
    times_finished = serializers.IntegerField()
    style = serializers.IntegerField()
