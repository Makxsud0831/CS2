from rest_framework import serializers
from .models import GameServer, ServerConfig, ServerMap


class ServerConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServerConfig
        exclude = ['server']


class GameServerSerializer(serializers.ModelSerializer):
    config = ServerConfigSerializer(read_only=True)

    class Meta:
        model = GameServer
        exclude = ['rcon_password']  # ← passwordni hech qachon expose qilma


class ServerMapSerializer(serializers.ModelSerializer):
    tier_display = serializers.SerializerMethodField()

    class Meta:
        model = ServerMap
        fields = [
            'id', 'server', 'name', 'workshop_id', 'map_type',
            'tier', 'tier_display', 'stages', 'bonus_count',
            'is_active', 'is_current', 'position_in_cycle',
            'play_count', 'avg_completion_time',
            'gravity', 'max_velocity',
        ]
        read_only_fields = ['play_count', 'avg_completion_time', 'is_current']

    TIER_NAMES = {
        0: 'Unrated', 1: 'Very Easy', 2: 'Easy', 3: 'Medium',
        4: 'Hard', 5: 'Very Hard', 6: 'Insane', 7: 'Extreme', 8: 'Death',
    }

    def get_tier_display(self, obj):
        return self.TIER_NAMES.get(obj.tier, 'Unrated')

    def validate_tier(self, value):
        if not 0 <= value <= 8:
            raise serializers.ValidationError("tier 0-8 oralig'ida bo'lishi kerak")
        return value