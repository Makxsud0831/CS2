from django.db import models
from django.conf import settings
from servers.models import ServerMap


# ──────────────────────────────────────────
# SharpTimer native jadvallar (managed=False)
# Django bu jadvallarni yaratmaydi/o'zgartirmaydi.
# SharpTimer o'zi yaratadi va yozadi.
# ──────────────────────────────────────────

class STPlayerRecord(models.Model):
    """
    SharpTimer ning 'PlayerRecords' jadvali.
    Har bir (SteamID, MapName, Style) uchun bitta PB.
    """
    SteamID = models.CharField(max_length=64, primary_key=True)
    MapName = models.CharField(max_length=128)
    PlayerName = models.CharField(max_length=128, blank=True)
    TimerTicks = models.IntegerField(default=0)
    FormattedTime = models.CharField(max_length=32)
    UnixStamp = models.IntegerField(default=0)
    TimesFinished = models.IntegerField(default=0)
    LastFinished = models.IntegerField(default=0)
    Style = models.IntegerField(default=0)
    Mode = models.TextField(default='Standard')

    class Meta:
        managed = False
        db_table = 'PlayerRecords'
        unique_together = [('SteamID', 'MapName', 'Style')]

    @property
    def time_ms(self):
        # SharpTimer 64-tick yoki 128-tick serverda ishlaydi
        # settings dan tickrate olamiz, default 128
        tickrate = getattr(settings, 'SERVER_TICKRATE', 128)
        return (self.TimerTicks / tickrate) * 1000

    @property
    def time_display(self):
        return self.FormattedTime

    def __str__(self):
        return f"{self.PlayerName} — {self.MapName} [{self.FormattedTime}]"


class STPlayerStats(models.Model):

    SteamID = models.CharField(max_length=64, primary_key=True)
    PlayerName = models.CharField(max_length=128, blank=True)
    GlobalPoints = models.IntegerField(default=0)
    TimesConnected = models.IntegerField(default=0)
    LastConnected = models.IntegerField(default=0)
    HideStats = models.BooleanField(default=False)

    class Meta:
        managed = False
        db_table = 'PlayerStats'

    def __str__(self):
        return f"{self.PlayerName} — {self.GlobalPoints}pts"


class PlayerRecord(models.Model):

    STYLE_NORMAL = 'normal'
    STYLE_SW = 'sw'         # sideways
    STYLE_HSW = 'hsw'       # half-sideways
    STYLE_WR = 'wr'         # world record style (low gravity)
    STYLE_AUTO = 'auto'     # autobhop

    STYLE_CHOICES = [
        (STYLE_NORMAL, 'Normal'),
        (STYLE_SW, 'Sideways'),
        (STYLE_HSW, 'Half-Sideways'),
        (STYLE_WR, 'WR Style'),
        (STYLE_AUTO, 'Auto-bhop'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='records',
    )
    map = models.ForeignKey(
        ServerMap,
        on_delete=models.CASCADE,
        related_name='records',
    )
    style = models.CharField(max_length=10, choices=STYLE_CHOICES, default=STYLE_NORMAL)

    # Vaqt millisekund da saqlanadi (float aniqlik uchun)
    time_ms = models.FloatField()

    # Qo'shimcha statistika
    jumps = models.IntegerField(default=0)
    strafes = models.IntegerField(default=0)
    sync = models.FloatField(default=0.0)       # strafe sync % (0-100)
    pre_speed = models.FloatField(default=0.0)  # start speed
    max_speed = models.FloatField(default=0.0)

    # Meta
    server = models.ForeignKey(
        'servers.GameServer',
        on_delete=models.SET_NULL,
        null=True,
        related_name='records',
    )
    set_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('user', 'map', 'style')]
        ordering = ['time_ms']
        indexes = [
            models.Index(fields=['map', 'style', 'time_ms']),
            models.Index(fields=['user', 'map']),
        ]

    def __str__(self):
        return f"{self.user} — {self.map} [{self.style}] {self.time_ms:.0f}ms"

    @property
    def time_seconds(self):
        return self.time_ms / 1000.0

    @property
    def time_display(self):
        total = self.time_ms / 1000.0
        minutes = int(total // 60)
        seconds = total % 60
        if minutes:
            return f"{minutes}:{seconds:06.3f}"
        return f"{seconds:.3f}"


class RecordHistory(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='record_history',
    )
    map = models.ForeignKey(
        ServerMap,
        on_delete=models.CASCADE,
        related_name='record_history',
    )
    style = models.CharField(max_length=10)
    time_ms = models.FloatField()
    jumps = models.IntegerField(default=0)
    set_at = models.DateTimeField()
    improvement_ms = models.FloatField(default=0.0)  # qancha yaxshilandi

    class Meta:
        ordering = ['-set_at']

    def __str__(self):
        return f"{self.user} — {self.map} [{self.style}] {self.time_ms:.0f}ms (history)"


class CheckpointStat(models.Model):
    """
    O'yinchining bitta mapdagi PB yugurishida ishlatgan !cp / !tp soni.
    SharpTimer jadvaliga tegmaymiz - alohida saqlaymiz, (SteamID, map, style) bo'yicha.
    Plagin run tugaganda Django'ga yuboradi (API token bilan).
    """
    steam_id = models.CharField(max_length=64)
    map_name = models.CharField(max_length=128)
    style = models.IntegerField(default=0)
    cp_count = models.IntegerField(default=0)
    tp_count = models.IntegerField(default=0)
    time_ms = models.FloatField(default=0.0)  # shu run vaqti (PB bilan moslashtirish uchun)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('steam_id', 'map_name', 'style')]
        indexes = [models.Index(fields=['map_name', 'style'])]

    def __str__(self):
        return f"{self.steam_id} @ {self.map_name}: {self.cp_count}cp/{self.tp_count}tp"


class MapCompletion(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='completions',
    )
    map = models.ForeignKey(
        ServerMap,
        on_delete=models.CASCADE,
        related_name='completions',
    )
    style = models.CharField(max_length=10, default=PlayerRecord.STYLE_NORMAL)
    count = models.IntegerField(default=1)
    last_played = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('user', 'map', 'style')]

    def __str__(self):
        return f"{self.user} — {self.map} x{self.count}"
