from rest_framework import serializers
from .models import User, SteamProfile, Subscription


class SteamProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = SteamProfile
        fields = ['steam_id64', 'profile_url', 'display_name', 'last_synced']
        read_only_fields = fields  # Steam OAuth boshqaradi, user o'zgartira olmaydi


class SubscriptionSerializer(serializers.ModelSerializer):
    is_active = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = Subscription
        fields = ['plan', 'started_at', 'expires_at', 'is_active', 'permissions']
        read_only_fields = fields

    def get_is_active(self, obj):
        return obj.is_active()

    def get_permissions(self, obj):
        return obj.get_permissions()


class UserMeSerializer(serializers.ModelSerializer):
    steam_profile = serializers.SerializerMethodField()
    subscription = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'avatar', 'steam_profile', 'subscription', 'created_at']
        read_only_fields = ['id', 'created_at']

    def get_steam_profile(self, obj):
        if hasattr(obj, 'steam_profile'):
            return SteamProfileSerializer(obj.steam_profile).data
        return None

    def get_subscription(self, obj):
        if hasattr(obj, 'subscription'):
            return SubscriptionSerializer(obj.subscription).data
        return None