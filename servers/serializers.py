from rest_framework import serializers
from .models import GameServer, ServerConfig


class ServerConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServerConfig
        exclude = ['server']


class GameServerSerializer(serializers.ModelSerializer):
    config = ServerConfigSerializer(read_only=True)

    class Meta:
        model = GameServer
        exclude = ['rcon_password']  # ← passwordni hech qachon expose qilma