from django.db import models


class GameServer(models.Model):
    name = models.CharField(max_length=100)
    ip = models.GenericIPAddressField()
    port = models.IntegerField(default=27015)
    rcon_password = models.CharField(max_length=128)
    region = models.CharField(max_length=50, default="uz")
    is_online = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.ip}:{self.port})"

    def get_address(self):
        return f"{self.ip}:{self.port}"


class ServerConfig(models.Model):
    BHOP = 'bhop'
    SURF = 'surf'
    DM = 'dm'
    KZ = 'kz'
    AIM = 'aim'

    GAMEMODE_CHOICES = [
        (BHOP, 'Bhop'),
        (SURF, 'Surf'),
        (DM, 'Deathmatch'),
        (KZ, 'KZ'),
        (AIM, 'Aim'),
    ]

    server = models.OneToOneField(GameServer, on_delete=models.CASCADE, related_name='config')
    gamemode = models.CharField(max_length=20, choices=GAMEMODE_CHOICES, default=BHOP)
    max_players = models.IntegerField(default=24)
    tickrate = models.IntegerField(default=128)
    timer_enabled = models.BooleanField(default=True)
    bhop_enabled = models.BooleanField(default=True)
    map_cycle_enabled = models.BooleanField(default=True)
    current_map = models.CharField(max_length=64, blank=True)


class ServerMap(models.Model):
    server = models.ForeignKey(GameServer, on_delete=models.CASCADE, related_name="maps")

    # Map identity
    name = models.CharField(max_length=64)  # de_dust2, bhop_arcane
    workshop_id = models.CharField(max_length=64, blank=True, null=True)

    # Map type
    MAP_TYPES = [
        ("vanilla", "Vanilla"),
        ("bhop", "Bhop"),
        ("surf", "Surf"),
        ("retake", "Retake"),
        ("dm", "Deathmatch"),
    ]
    map_type = models.CharField(max_length=20, choices=MAP_TYPES, default="vanilla")

    # Rotation system
    is_active = models.BooleanField(default=True)
    is_current = models.BooleanField(default=False)
    position_in_cycle = models.IntegerField(default=0)

    # Performance tracking
    play_count = models.IntegerField(default=0)
    avg_completion_time = models.FloatField(default=0.0)

    # Workshop / file data
    file_path = models.CharField(max_length=255, blank=True)
    download_url = models.URLField(blank=True)

    # Rules override per map
    gravity = models.FloatField(default=1.0)
    max_velocity = models.IntegerField(default=3500)

    def __str__(self):
        return self.name


class MapConfig(models.Model):
    server_map = models.OneToOneField(ServerMap, on_delete=models.CASCADE, related_name='config')
    gravity = models.FloatField(default=1.0)
    max_velocity = models.IntegerField(default=3500)
    air_accelerate = models.FloatField(default=800)
    bhop_enabled = models.BooleanField(default=True)
    auto_bhop = models.BooleanField(default=False)

    def to_cfg(self):
        return f"""
                    sv_gravity {int(self.gravity * 800)}
                    sv_maxvelocity {self.max_velocity}
                    sv_airaccelerate {self.air_accelerate}
                    sv_enablebunnyhopping {int(self.bhop_enabled)}
                    sv_autobunnyhopping {int(self.auto_bhop)}
                    """
