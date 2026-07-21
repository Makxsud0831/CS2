from django.core.cache import cache
from rest_framework.views import APIView
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework.response import Response
from .models import GameServer, ServerMap
from .services import RCONService, ServerQueryService, ServerLauncher, rcon_command_allowed
from .serializers import GameServerSerializer, ServerMapSerializer


class ServerListView(generics.ListAPIView):
    queryset = GameServer.objects.all()
    serializer_class = GameServerSerializer
    permission_classes = [IsAuthenticated]


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def server_status(request, pk):
    try:
        server = GameServer.objects.get(pk=pk)
    except GameServer.DoesNotExist:
        return Response({'error': 'Topilmadi'}, status=404)

    qs = ServerQueryService(server)
    info = qs.get_info()
    players = qs.get_players()

    if not info:
        return Response({'online': False})

    return Response({
        'online': True,
        'name': info.server_name,
        'map': info.map_name,
        'players': info.player_count,
        'max_players': info.max_players,
        'player_list': [
            {'name': p.name, 'score': p.score, 'duration': p.duration}
            for p in players
        ]
    })


@api_view(['POST'])
@permission_classes([IsAdminUser])
def rcon_command(request, pk):
    try:
        server = GameServer.objects.get(pk=pk)
    except GameServer.DoesNotExist:
        return Response({'error': 'Topilmadi'}, status=404)

    command = request.data.get('command')
    if not command:
        return Response({'error': 'command majburiy'}, status=400)

    ok, reason = rcon_command_allowed(command)
    if not ok:
        return Response({'error': reason}, status=403)

    rcon = RCONService(server)
    result = rcon.execute(command)
    return Response({'result': result})


@api_view(['POST'])
@permission_classes([IsAdminUser])
def change_map(request, pk):
    server = GameServer.objects.get(pk=pk)
    map_name = request.data.get('map')
    rcon = RCONService(server)
    result = rcon.change_map(map_name)
    return Response({'result': result})


class ServerStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, server_id):
        try:
            server = GameServer.objects.get(id=server_id)
        except GameServer.DoesNotExist:
            return Response({'error': 'Server topilmadi'}, status=404)

        cache_key = f'srv_status_{server_id}'
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        query = ServerQueryService(server)
        info = query.get_info(timeout=3)
        is_online = info is not None
        GameServer.objects.filter(id=server_id).update(is_online=is_online)

        if not is_online:
            data = {'online': False, 'server_id': server_id}
            cache.set(cache_key, data, 20)
            return Response(data)

        players = query.get_players()
        data = {
            'online': True,
            'server_id': server_id,
            'name': info.server_name,
            'map': info.map_name,
            'players': info.player_count,
            'max_players': info.max_players,
            'player_list': [
                {'name': p.name, 'score': p.score, 'duration': round(p.duration)}
                for p in players
            ],
        }
        cache.set(cache_key, data, 20)
        return Response(data)


@api_view(['GET'])
@permission_classes([AllowAny])
def public_server_status(request):
    """Bosh sahifa uchun barcha serverlarning jonli holati (anonim ham ko'radi).
    A2S so'rovi 20s keshlanadi (ServerStatusView bilan bir xil kesh kaliti)."""
    out = []
    for s in GameServer.objects.all().order_by('port'):
        ck = f'pub_status_{s.id}'
        cached = cache.get(ck)
        if cached is None:
            info = ServerQueryService(s).get_info(timeout=3)
            if info:
                cached = {'online': True, 'map': info.map_name,
                          'players': info.player_count, 'max_players': info.max_players}
            else:
                cached = {'online': False}
            cache.set(ck, cached, 20)
            GameServer.objects.filter(id=s.id).update(is_online=cached['online'])
        out.append({
            'id': s.id,
            'online': cached.get('online', False),
            'players': cached.get('players', 0),
            'max_players': cached.get('max_players', 0),
            'map': cached.get('map') or s.current_map,
        })
    return Response({'servers': out})


class RCONCommandView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, server_id):
        try:
            server = GameServer.objects.get(id=server_id)
        except GameServer.DoesNotExist:
            return Response({'error': 'Server topilmadi'}, status=404)

        command = request.data.get('command', '').strip()
        if not command:
            return Response({'error': 'command maydoni bo\'sh'}, status=400)

        ok, reason = rcon_command_allowed(command)
        if not ok:
            return Response({'error': reason}, status=403)

        rcon = RCONService(server)
        result = rcon.execute(command)

        return Response({
            'server_id': server_id,
            'command': command,
            'result': result
        })


class ChangeMapView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, server_id):
        try:
            server = GameServer.objects.get(id=server_id)
        except GameServer.DoesNotExist:
            return Response({'error': 'Server topilmadi'}, status=404)

        map_name = request.data.get('map', '').strip()
        if not map_name:
            return Response({'error': 'map maydoni bo\'sh'}, status=400)

        rcon = RCONService(server)
        result = rcon.change_map(map_name)

        if hasattr(server, 'config'):
            server.config.current_map = map_name
            server.config.save()

        return Response({
            'server_id': server_id,
            'map': map_name,
            'result': result
        })


class KickPlayerView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, server_id):
        try:
            server = GameServer.objects.get(id=server_id)
        except GameServer.DoesNotExist:
            return Response({'error': 'Server topilmadi'}, status=404)

        steam_id = request.data.get('steam_id', '').strip()
        if not steam_id:
            return Response({'error': 'steam_id maydoni bo\'sh'}, status=400)

        rcon = RCONService(server)
        result = rcon.kick_player(steam_id)

        return Response({
            'server_id': server_id,
            'kicked': steam_id,
            'result': result
        })


class BanPlayerView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, server_id):
        try:
            server = GameServer.objects.get(id=server_id)
        except GameServer.DoesNotExist:
            return Response({'error': 'Server topilmadi'}, status=404)

        steam_id = request.data.get('steam_id', '').strip()
        if not steam_id:
            return Response({'error': 'steam_id majburiy'}, status=400)

        duration = int(request.data.get('duration', 0))
        rcon = RCONService(server)
        result = rcon.ban_player(steam_id, duration)

        return Response({
            'server_id': server_id,
            'banned': steam_id,
            'duration_minutes': duration,
            'result': result
        })


class UnbanPlayerView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, server_id):
        try:
            server = GameServer.objects.get(id=server_id)
        except GameServer.DoesNotExist:
            return Response({'error': 'Server topilmadi'}, status=404)

        steam_id = request.data.get('steam_id', '').strip()
        if not steam_id:
            return Response({'error': 'steam_id majburiy'}, status=400)

        rcon = RCONService(server)
        result = rcon.unban_player(steam_id)
        return Response({'server_id': server_id, 'unbanned': steam_id, 'result': result})


class SayView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, server_id):
        try:
            server = GameServer.objects.get(id=server_id)
        except GameServer.DoesNotExist:
            return Response({'error': 'Server topilmadi'}, status=404)

        message = request.data.get('message', '').strip()
        if not message:
            return Response({'error': 'message majburiy'}, status=400)

        rcon = RCONService(server)
        result = rcon.say(message)
        return Response({'server_id': server_id, 'message': message, 'result': result})


class RestartView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, server_id):
        try:
            server = GameServer.objects.get(id=server_id)
        except GameServer.DoesNotExist:
            return Response({'error': 'Server topilmadi'}, status=404)

        rcon = RCONService(server)
        result = rcon.restart_server()
        return Response({'server_id': server_id, 'result': result})


class StartServerView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, server_id):
        try:
            server = GameServer.objects.get(id=server_id)
        except GameServer.DoesNotExist:
            return Response({'error': 'Server topilmadi'}, status=404)

        if ServerQueryService(server).get_info() is not None:
            return Response({'server_id': server_id, 'started': False,
                             'message': 'Server allaqachon ishlab turibdi'}, status=409)

        ok, message = ServerLauncher(server).start()
        status_code = status.HTTP_200_OK if ok else status.HTTP_400_BAD_REQUEST
        return Response({'server_id': server_id, 'started': ok, 'message': message},
                        status=status_code)


class StopServerView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, server_id):
        try:
            server = GameServer.objects.get(id=server_id)
        except GameServer.DoesNotExist:
            return Response({'error': 'Server topilmadi'}, status=404)

        result = RCONService(server).execute('quit')
        GameServer.objects.filter(id=server_id).update(is_online=False)
        return Response({'server_id': server_id, 'stopped': True, 'result': result})


class PlayersWithIDsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, server_id):
        try:
            server = GameServer.objects.get(id=server_id)
        except GameServer.DoesNotExist:
            return Response({'error': 'Server topilmadi'}, status=404)

        # RCON 'users' orqali (A2S CS2'da o'yinchi nomini bermaydi)
        players = RCONService(server).get_players_with_ids()
        return Response({'server_id': server_id, 'players': players, 'count': len(players)})


class ExecCfgView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, server_id):
        try:
            server = GameServer.objects.get(id=server_id)
        except GameServer.DoesNotExist:
            return Response({'error': 'Server topilmadi'}, status=404)

        cfg = request.data.get('cfg', '').strip()
        if not cfg:
            return Response({'error': 'cfg majburiy'}, status=400)

        rcon = RCONService(server)
        result = rcon.exec_cfg(cfg)
        return Response({'server_id': server_id, 'cfg': cfg, 'result': result})


# ──────────────────────────────────────────
# Map Pool
# ──────────────────────────────────────────

class MapPoolView(generics.ListCreateAPIView):
    serializer_class = ServerMapSerializer

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAdminUser()]
        return [IsAuthenticated()]

    def get_queryset(self):
        qs = ServerMap.objects.filter(server_id=self.kwargs['server_id'])

        map_type = self.request.query_params.get('type')
        if map_type:
            qs = qs.filter(map_type=map_type)

        tier = self.request.query_params.get('tier')
        if tier is not None and tier.isdigit():
            qs = qs.filter(tier=int(tier))

        active = self.request.query_params.get('active')
        if active is not None:
            qs = qs.filter(is_active=active.lower() == 'true')

        return qs.order_by('tier', 'name')

    def perform_create(self, serializer):
        serializer.save(server_id=self.kwargs['server_id'])


class MapDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ServerMapSerializer
    lookup_url_kwarg = 'map_id'

    def get_permissions(self):
        if self.request.method in ('PATCH', 'PUT', 'DELETE'):
            return [IsAdminUser()]
        return [IsAuthenticated()]

    def get_queryset(self):
        return ServerMap.objects.filter(server_id=self.kwargs['server_id'])


class SetCurrentMapView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, server_id, map_id):
        try:
            server = GameServer.objects.get(id=server_id)
        except GameServer.DoesNotExist:
            return Response({'error': 'Server topilmadi'}, status=404)

        try:
            server_map = ServerMap.objects.get(id=map_id, server=server)
        except ServerMap.DoesNotExist:
            return Response({'error': 'Map topilmadi'}, status=404)

        if not server_map.is_active:
            return Response({'error': 'Bu map pool da faol emas'}, status=400)

        rcon = RCONService(server)
        if server_map.workshop_id:
            result = rcon.execute(f"host_workshop_map {server_map.workshop_id}")
        else:
            result = rcon.change_map(server_map.name)

        ServerMap.objects.filter(server=server).update(is_current=False)
        ServerMap.objects.filter(id=map_id).update(
            is_current=True,
            play_count=server_map.play_count + 1,
        )

        if hasattr(server, 'config'):
            server.config.current_map = server_map.name
            server.config.save()

        return Response({
            'server_id': server_id,
            'map': server_map.name,
            'workshop_id': server_map.workshop_id,
            'result': result,
        })
