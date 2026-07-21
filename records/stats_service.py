from dataclasses import dataclass, field
from typing import List, Optional

from django.db import models
from django.db.models import Count, Min

from .models import STPlayerRecord, STPlayerStats


@dataclass
class PlayerStatsResult:
    steam_id: str
    steam_name: str
    global_points: int
    total_maps_completed: int
    total_runs: int
    rank: int
    total_players: int
    top_records: list = field(default_factory=list)


class SharpTimerStatsService:

    def get_player_stats(self, steam_id: str) -> Optional[PlayerStatsResult]:
        try:
            stats = STPlayerStats.objects.get(SteamID=steam_id)
        except STPlayerStats.DoesNotExist:
            return None

        records = STPlayerRecord.objects.filter(SteamID=steam_id)
        total_maps = records.values('MapName').distinct().count()
        total_runs = records.aggregate(total=Count('TimesFinished'))
        # TimesFinished har bir mapda to'planadi, total runs = yig'indisi
        total_runs_count = sum(r.TimesFinished for r in records)

        rank = (
            STPlayerStats.objects
            .filter(GlobalPoints__gt=stats.GlobalPoints)
            .count()
        ) + 1
        total_players = STPlayerStats.objects.count()

        top_records = list(
            records.order_by('TimerTicks')[:10]
        )

        return PlayerStatsResult(
            steam_id=steam_id,
            steam_name=stats.PlayerName,
            global_points=stats.GlobalPoints,
            total_maps_completed=total_maps,
            total_runs=total_runs_count,
            rank=rank,
            total_players=total_players,
            top_records=top_records,
        )

    def get_map_leaderboard(self, map_name: str, style: int = 0, limit: int = 100):
        records = (
            STPlayerRecord.objects
            .filter(MapName=map_name, Style=style)
            .order_by('TimerTicks')[:limit]
        )
        result = []
        for rank, rec in enumerate(records, start=1):
            result.append({
                'rank': rank,
                'steam_id': rec.SteamID,
                'steam_name': rec.PlayerName,
                'time_display': rec.FormattedTime,
                'time_ms': rec.time_ms,
                'times_finished': rec.TimesFinished,
                'style': rec.Style,
            })
        return result

    def get_global_top(self, limit: int = 50):
        return (
            STPlayerStats.objects
            .filter(HideStats=False)
            .order_by('-GlobalPoints')[:limit]
        )

    def get_recent_records(self, map_name: str = None, limit: int = 20):
        qs = STPlayerRecord.objects.all()
        if map_name:
            qs = qs.filter(MapName=map_name)
        return qs.order_by('-UnixStamp')[:limit]

    def search_players(self, query: str, limit: int = 20):
        return (
            STPlayerStats.objects
            .filter(HideStats=False)
            .filter(
                models.Q(PlayerName__icontains=query) |
                models.Q(SteamID__icontains=query)
            )
            .order_by('-GlobalPoints')[:limit]
        )
