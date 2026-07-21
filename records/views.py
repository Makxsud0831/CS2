from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response

from servers.models import ServerMap
from .models import PlayerRecord, RecordHistory, MapCompletion, CheckpointStat
from .serializers import PlayerRecordSerializer, RecordHistorySerializer, MapCompletionSerializer
from .services import RecordService, RunResult
from .permissions import IsTrustedServer
from .stats_service import SharpTimerStatsService
from .stats_serializers import (
    STPlayerStatsSerializer,
    PlayerStatsSerializer,
    MapLeaderboardEntrySerializer,
    STRecordSerializer,
)


class MapLeaderboardView(generics.ListAPIView):
    serializer_class = PlayerRecordSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        map_id = self.kwargs['map_id']
        style = self.request.query_params.get('style', PlayerRecord.STYLE_NORMAL)
        return (
            PlayerRecord.objects
            .filter(map_id=map_id, style=style)
            .select_related('user', 'user__steam_profile', 'map')
            .order_by('time_ms')
        )


class PlayerRecordsView(generics.ListAPIView):
    serializer_class = PlayerRecordSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return (
            PlayerRecord.objects
            .filter(user_id=self.kwargs['user_id'])
            .select_related('user', 'user__steam_profile', 'map')
            .order_by('map__name', 'style')
        )


class MyRecordsView(generics.ListAPIView):

    serializer_class = PlayerRecordSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            PlayerRecord.objects
            .filter(user=self.request.user)
            .select_related('user', 'user__steam_profile', 'map')
            .order_by('map__name', 'style')
        )


class MyHistoryView(generics.ListAPIView):
    """GET /api/records/me/history/?map_id=<id>&style=normal"""
    serializer_class = RecordHistorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = RecordHistory.objects.filter(user=self.request.user)
        map_id = self.request.query_params.get('map_id')
        style = self.request.query_params.get('style')
        if map_id:
            qs = qs.filter(map_id=map_id)
        if style:
            qs = qs.filter(style=style)
        return qs.order_by('-set_at')


class MyCompletionsView(generics.ListAPIView):
    serializer_class = MapCompletionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            MapCompletion.objects
            .filter(user=self.request.user)
            .select_related('map')
            .order_by('-last_played')
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_run(request):
    data = request.data
    map_id = data.get('map_id')
    time_ms = data.get('time_ms')

    if not map_id or time_ms is None:
        return Response({'error': 'map_id va time_ms majburiy'}, status=400)

    if not ServerMap.objects.filter(pk=map_id).exists():
        return Response({'error': 'Map topilmadi'}, status=404)

    try:
        time_ms = float(time_ms)
        if time_ms <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return Response({'error': "time_ms musbat son bo'lishi kerak"}, status=400)

    style = data.get('style', PlayerRecord.STYLE_NORMAL)
    if style not in dict(PlayerRecord.STYLE_CHOICES):
        return Response({'error': f"Noto'g'ri style: {style}"}, status=400)

    run = RunResult(
        user_id=request.user.pk,
        map_id=map_id,
        style=style,
        time_ms=time_ms,
        jumps=int(data.get('jumps', 0)),
        strafes=int(data.get('strafes', 0)),
        sync=float(data.get('sync', 0.0)),
        pre_speed=float(data.get('pre_speed', 0.0)),
        max_speed=float(data.get('max_speed', 0.0)),
        server_id=data.get('server_id'),
    )

    result = RecordService().submit_run(run)

    return Response({
        'is_pb': result.is_pb,
        'is_wr': result.is_wr,
        'rank': result.rank,
        'improvement_ms': result.improvement_ms,
        'record': PlayerRecordSerializer(result.record).data,
    }, status=status.HTTP_200_OK)


# ──────────────────────────────────────────
# SharpTimer stats views
# ──────────────────────────────────────────

@api_view(['GET'])
@permission_classes([AllowAny])
def player_stats(request, steam_id):
    result = SharpTimerStatsService().get_player_stats(steam_id)
    if result is None:
        return Response({'error': 'Player topilmadi'}, status=404)

    serializer = PlayerStatsSerializer({
        'steam_id': result.steam_id,
        'steam_name': result.steam_name,
        'global_points': result.global_points,
        'total_maps_completed': result.total_maps_completed,
        'total_runs': result.total_runs,
        'rank': result.rank,
        'total_players': result.total_players,
        'top_records': result.top_records,
    })
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_stats(request):

    steam_id = request.user.get_steam_id()
    if not steam_id:
        return Response({'error': 'Steam profil ulanmagan'}, status=400)

    result = SharpTimerStatsService().get_player_stats(steam_id)
    if result is None:
        return Response({'error': 'SharpTimer da hali rekord yo\'q'}, status=404)

    serializer = PlayerStatsSerializer({
        'steam_id': result.steam_id,
        'steam_name': result.steam_name,
        'global_points': result.global_points,
        'total_maps_completed': result.total_maps_completed,
        'total_runs': result.total_runs,
        'rank': result.rank,
        'total_players': result.total_players,
        'top_records': result.top_records,
    })
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([AllowAny])
def st_map_leaderboard(request, map_name):
    style = int(request.query_params.get('style', 0))
    limit = min(int(request.query_params.get('limit', 100)), 200)

    entries = SharpTimerStatsService().get_map_leaderboard(map_name, style=style, limit=limit)
    serializer = MapLeaderboardEntrySerializer(entries, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([AllowAny])
def global_top(request):

    limit = min(int(request.query_params.get('limit', 50)), 200)
    players = SharpTimerStatsService().get_global_top(limit=limit)
    serializer = STPlayerStatsSerializer(players, many=True)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsTrustedServer])
def submit_checkpoints(request):
    """
    POST /api/records/checkpoints/
    CS2 server (API token bilan) run tugaganda cp/tp sonini yuboradi.
    Body: { steam_id, map_name, style, cp_count, tp_count, time_ms }
    """
    data = request.data
    steam_id = str(data.get('steam_id', '')).strip()
    map_name = str(data.get('map_name', '')).strip()
    if not steam_id or not map_name:
        return Response({'error': 'steam_id va map_name majburiy'}, status=400)

    try:
        style = int(data.get('style', 0))
        cp_count = max(0, int(data.get('cp_count', 0)))
        tp_count = max(0, int(data.get('tp_count', 0)))
        time_ms = float(data.get('time_ms', 0))
    except (TypeError, ValueError):
        return Response({'error': "son maydonlari noto'g'ri"}, status=400)

    obj, _ = CheckpointStat.objects.update_or_create(
        steam_id=steam_id, map_name=map_name, style=style,
        defaults={'cp_count': cp_count, 'tp_count': tp_count, 'time_ms': time_ms},
    )
    return Response({'ok': True, 'steam_id': steam_id, 'map_name': map_name,
                     'cp_count': obj.cp_count, 'tp_count': obj.tp_count})


@api_view(['GET'])
@permission_classes([AllowAny])
def search_players(request):
    query = request.query_params.get('q', '').strip()
    if len(query) < 2:
        return Response({'error': "Qidiruv so'zi kamida 2 ta belgi bo'lishi kerak"}, status=400)

    limit = min(int(request.query_params.get('limit', 20)), 50)

    # SharpTimer o'yinchilari
    st_players = SharpTimerStatsService().search_players(query, limit=limit)
    st_results = STPlayerStatsSerializer(st_players, many=True).data

    # Panel userlari (username yoki steam display_name bo'yicha)
    from django.contrib.auth import get_user_model
    from django.db.models import Q
    User = get_user_model()
    panel_users = (
        User.objects
        .filter(
            Q(username__icontains=query) |
            Q(steam_profile__display_name__icontains=query) |
            Q(steam_profile__steam_id64__icontains=query)
        )
        .select_related('steam_profile')[:limit]
    )
    panel_results = [
        {
            'id': u.id,
            'username': u.username,
            'steam_id': u.get_steam_id(),
            'display_name': getattr(getattr(u, 'steam_profile', None), 'display_name', ''),
        }
        for u in panel_users
    ]

    return Response({
        'query': query,
        'panel_users': panel_results,
        'st_players': st_results,
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def recent_records(request):
    map_name = request.query_params.get('map')
    limit = min(int(request.query_params.get('limit', 20)), 100)

    records = SharpTimerStatsService().get_recent_records(map_name=map_name, limit=limit)
    serializer = STRecordSerializer(records, many=True)
    return Response(serializer.data)
