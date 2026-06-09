from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Subscription, SteamProfile


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ['username', 'email', 'is_premium', 'is_admin', 'created_at']
    fieldsets = UserAdmin.fieldsets + (
        ('Extra', {'fields': ('avatar',)}),
    )


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ['user', 'plan', 'is_active', 'expires_at']


@admin.register(SteamProfile)
class SteamProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'steam_id64', 'display_name', 'last_synced']
