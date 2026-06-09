from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import GameServer
from .services import ServerQueryService

from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from .models import GameServer
from .services import RCONService, ServerQueryService
from .serializers import GameServerSerializer


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

        query = ServerQueryService(server)
        info = query.get_info()       # None qaytaradi xato bo'lsa
        players = query.get_players() # [] qaytaradi xato bo'lsa

        # DB dagi is_online ni yangilash
        is_online = info is not None
        GameServer.objects.filter(id=server_id).update(is_online=is_online)

        if not is_online:
            return Response({'online': False, 'server_id': server_id})

        return Response({
            'online': True,
            'server_id': server_id,
            'name': info.server_name,
            'map': info.map_name,
            'players': info.player_count,
            'max_players': info.max_players,
            'player_list': [
                {
                    'name': p.name,
                    'score': p.score,
                    'duration': round(p.duration)
                }
                for p in players
            ]
        })


class RCONCommandView(APIView):
    """
    POST /api/servers/<id>/rcon/
    Serverga ixtiyoriy RCON buyrug'i yuboradi
    Body: { "command": "status" }
    Permissions: faqat admin (is_staff=True)

    Misol buyruqlar:
      status          → server holatini ko'rsatadi
      sv_cheats 1     → cheatlarni yoqadi
      map de_dust2    → mapni o'zgartiradi
      users           → barcha ulanishlarni ko'rsatadi
    """
    permission_classes = [IsAdminUser]

    def post(self, request, server_id):
        # Serverni DB dan topamiz
        try:
            server = GameServer.objects.get(id=server_id)
        except GameServer.DoesNotExist:
            return Response({'error': 'Server topilmadi'}, status=404)

        # Request body dan commandni olamiz
        command = request.data.get('command', '').strip()
        if not command:
            return Response({'error': 'command maydoni bo\'sh'}, status=400)

        # RCON orqali buyruqni serverga yuboramiz
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
