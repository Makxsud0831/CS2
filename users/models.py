from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def get_steam_id(self):
        if hasattr(self, 'steam_profile'):
            return self.steam_profile.steam_id64
        return None

    @property
    def steam_display_name(self):
        """Steam'dagi chiroyli nom (yo'q bo'lsa username)."""
        if hasattr(self, 'steam_profile') and self.steam_profile.display_name:
            return self.steam_profile.display_name
        return self.username

    @property
    def steam_avatar(self):
        """Steam statik avatar URL (yo'q bo'lsa bo'sh)."""
        if hasattr(self, 'steam_profile'):
            return self.steam_profile.avatar_url
        return ''

    def is_premium(self):
        return hasattr(self, 'subscription') and self.subscription.is_active()

    def is_admin(self):
        return self.is_staff or self.is_superuser


class BasePermission:
    permissions = []

    @classmethod
    def get_permissions(cls):
        return cls.permissions


class BasicPermission(BasePermission):
    permissions = ['bhop', 'speedometer']


class ProPermission(BasePermission):
    permissions = ['bhop', 'speedometer', 'doublejump', 'extra_hp']


class VIPPermission(BasePermission):
    permissions = ['bhop', 'speedometer', 'doublejump', 'extra_hp', 'noclip', 'custom_tag']


class Subscription(models.Model):
    BASIC = 'basic'
    PRO = 'pro'
    VIP = 'vip'

    PLAN_CHOICES = [
        (BASIC, 'Basic'),
        (PRO, 'Pro'),
        (VIP, 'VIP'),
    ]

    PERMISSION_CLASSES = {
        BASIC: BasicPermission,
        PRO: ProPermission,
        VIP: VIPPermission,
    }

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='subscription')
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default=BASIC)
    started_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    # VIP tugaganda skinlar arxivlanganmi (expire_vips komandasi qo'yadi)
    skins_archived = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user} - {self.plan}"

    def is_active(self):
        from django.utils import timezone
        return self.expires_at > timezone.now()

    def get_permissions(self):
        permission_class = self.PERMISSION_CLASSES.get(self.plan, BasePermission)
        return permission_class.get_permissions()

    def has_permission(self, permission):
        return permission in self.get_permissions() and self.is_active()


class SkinBackup(models.Model):
    """VIP tugaganda saqlangan WeaponPaints loadout (VIP qayta olinganda tiklanadi)."""
    steam_id = models.CharField(max_length=64, unique=True)
    data = models.JSONField()
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"SkinBackup({self.steam_id})"


class SteamProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='steam_profile')
    steam_id64 = models.CharField(max_length=64, unique=True)
    profile_url = models.URLField(blank=True)
    display_name = models.CharField(max_length=128, blank=True)
    avatar_url = models.URLField(blank=True)  # Steam statik avatar (avatarfull)
    last_synced = models.DateTimeField(null=True, blank=True)
    # FACEIT integratsiyasi
    faceit_level = models.IntegerField(null=True, blank=True)  # oxirgi tekshirilgan level (1-10)
    faceit_vip_granted = models.BooleanField(default=False)    # bir martalik FACEIT VIP berilganmi

    def __str__(self):
        return f"{self.display_name} ({self.steam_id64})"

    def sync(self):
        """Steam API dan ma'lumotlarni yangilaydi"""
        from django.utils import timezone
        # keyinroq Steam API bilan to'ldiramiz
        self.last_synced = timezone.now()
        self.save()
