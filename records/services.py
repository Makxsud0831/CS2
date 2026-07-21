import logging
from dataclasses import dataclass
from typing import Optional

from django.db import transaction
from django.utils import timezone

from .models import PlayerRecord, RecordHistory, MapCompletion

logger = logging.getLogger(__name__)


@dataclass
class RunResult:
    """CS2 serveridan kelgan bitta run natijasi"""
    user_id: int
    map_id: int
    style: str
    time_ms: float
    jumps: int = 0
    strafes: int = 0
    sync: float = 0.0
    pre_speed: float = 0.0
    max_speed: float = 0.0
    server_id: Optional[int] = None


@dataclass
class SaveResult:
    is_pb: bool                        # Personal Best bo'ldimi
    is_wr: bool                        # World Record bo'ldimi
    rank: int                          # Yangi rank
    improvement_ms: float              # Oldingi PB dan qancha yaxshilandi (0 if first run)
    record: PlayerRecord


class RecordService:
    """
    Run natijasini qabul qilib, PB ni yangilaydi yoki yangi yozadi.
    """

    @transaction.atomic
    def submit_run(self, run: RunResult) -> SaveResult:
        existing = PlayerRecord.objects.filter(
            user_id=run.user_id,
            map_id=run.map_id,
            style=run.style,
        ).first()

        is_pb = existing is None or run.time_ms < existing.time_ms
        improvement_ms = 0.0

        if existing and is_pb:
            improvement_ms = existing.time_ms - run.time_ms
            RecordHistory.objects.create(
                user_id=run.user_id,
                map_id=run.map_id,
                style=run.style,
                time_ms=existing.time_ms,
                jumps=existing.jumps,
                set_at=existing.set_at,
                improvement_ms=improvement_ms,
            )
            existing.time_ms = run.time_ms
            existing.jumps = run.jumps
            existing.strafes = run.strafes
            existing.sync = run.sync
            existing.pre_speed = run.pre_speed
            existing.max_speed = run.max_speed
            existing.server_id = run.server_id
            existing.set_at = timezone.now()
            existing.save()
            record = existing

        elif not existing:
            record = PlayerRecord.objects.create(
                user_id=run.user_id,
                map_id=run.map_id,
                style=run.style,
                time_ms=run.time_ms,
                jumps=run.jumps,
                strafes=run.strafes,
                sync=run.sync,
                pre_speed=run.pre_speed,
                max_speed=run.max_speed,
                server_id=run.server_id,
            )
        else:
            record = existing

        self._update_completion(run)

        rank = (
            PlayerRecord.objects
            .filter(map_id=run.map_id, style=run.style, time_ms__lte=record.time_ms)
            .count()
        )

        is_wr = rank == 1 and is_pb

        if is_pb:
            logger.info(
                'New PB: user=%s map=%s style=%s time=%.3fs rank=%d',
                run.user_id, run.map_id, run.style, run.time_ms / 1000, rank,
            )

        return SaveResult(
            is_pb=is_pb,
            is_wr=is_wr,
            rank=rank,
            improvement_ms=improvement_ms,
            record=record,
        )

    def _update_completion(self, run: RunResult):
        obj, created = MapCompletion.objects.get_or_create(
            user_id=run.user_id,
            map_id=run.map_id,
            style=run.style,
        )
        if not created:
            MapCompletion.objects.filter(pk=obj.pk).update(count=obj.count + 1)
