from django.test import TestCase
from django.contrib.auth import get_user_model
from unittest.mock import patch, MagicMock
from rest_framework.test import APIClient
from rest_framework import status
from .models import GameServer, ServerConfig

User = get_user_model()


class BaseTestCase(TestCase):
    """Barcha testlar uchun umumiy setup"""

    def setUp(self):
        self.client = APIClient()

        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.admin = User.objects.create_superuser(
            username='admin',
            password='adminpass123'
        )
        self.server = GameServer.objects.create(
            name='Test CS2 Server',
            ip='192.168.1.1',
            port=27015,
            rcon_password='secret123',
            region='uz'
        )


# ──────────────────────────────────────────
# 1. ServerStatusView
# ──────────────────────────────────────────
class ServerStatusViewTest(BaseTestCase):

    def test_unauthenticated_user_blocked(self):
        """Login qilmagan user 401 yoki 403 olishi kerak"""
        response = self.client.get(f'/api/servers/{self.server.id}/status/')
        # DRF SessionAuthentication → 403, TokenAuthentication → 401
        # ikkalasi ham to'g'ri — faqat 200 bo'lmasin
        self.assertIn(
            response.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]
        )

    @patch('servers.views.ServerQueryService')
    def test_server_online(self, mock_qs):
        """Server online bo'lsa to'liq ma'lumot qaytarishi kerak"""
        mock_info = MagicMock()
        mock_info.server_name = 'Test CS2 Server'
        mock_info.map_name = 'bhop_arcane'
        mock_info.player_count = 3
        mock_info.max_players = 24

        mock_player = MagicMock()
        mock_player.name = 'xX_Player_Xx'
        mock_player.score = 10
        mock_player.duration = 342.5

        mock_qs.return_value.get_info.return_value = mock_info
        mock_qs.return_value.get_players.return_value = [mock_player]

        self.client.force_authenticate(user=self.user)
        response = self.client.get(f'/api/servers/{self.server.id}/status/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['online'])
        self.assertEqual(response.data['map'], 'bhop_arcane')
        self.assertEqual(response.data['players'], 3)
        self.assertEqual(len(response.data['player_list']), 1)

    @patch('servers.views.ServerQueryService')
    def test_server_offline(self, mock_qs):
        """Server offline bo'lsa online: False qaytarishi kerak"""
        mock_qs.return_value.get_info.return_value = None
        mock_qs.return_value.get_players.return_value = []

        self.client.force_authenticate(user=self.user)
        response = self.client.get(f'/api/servers/{self.server.id}/status/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['online'])

    @patch('servers.views.ServerQueryService')
    def test_db_is_online_updated(self, mock_qs):
        """Server offline bo'lsa DB dagi is_online False bo'lishi kerak"""
        mock_qs.return_value.get_info.return_value = None
        mock_qs.return_value.get_players.return_value = []

        self.client.force_authenticate(user=self.user)
        self.client.get(f'/api/servers/{self.server.id}/status/')

        self.server.refresh_from_db()
        self.assertFalse(self.server.is_online)

    def test_server_not_found(self):
        """Mavjud bo'lmagan server 404 qaytarishi kerak"""
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/servers/9999/status/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


# ──────────────────────────────────────────
# 2. RCONCommandView
# ──────────────────────────────────────────
class RCONCommandViewTest(BaseTestCase):

    def test_regular_user_blocked(self):
        """Admin bo'lmagan user 403 olishi kerak"""
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            f'/api/servers/{self.server.id}/rcon/',
            {'command': 'status'}
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_empty_command_rejected(self):
        """Bo'sh command 400 qaytarishi kerak"""
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            f'/api/servers/{self.server.id}/rcon/',
            {'command': ''}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('servers.views.RCONService')
    def test_valid_command_executed(self, mock_rcon):
        """To'g'ri command RCON ga yuborilishi kerak"""
        mock_rcon.return_value.execute.return_value = 'hostname: Test CS2 Server'

        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            f'/api/servers/{self.server.id}/rcon/',
            {'command': 'status'},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['command'], 'status')
        self.assertIn('result', response.data)
        mock_rcon.return_value.execute.assert_called_once_with('status')


# ──────────────────────────────────────────
# 3. ChangeMapView
# ──────────────────────────────────────────
class ChangeMapViewTest(BaseTestCase):

    def test_empty_map_rejected(self):
        """Bo'sh map nomi 400 qaytarishi kerak"""
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            f'/api/servers/{self.server.id}/map/',
            {'map': ''},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('servers.views.RCONService')
    def test_map_changed(self, mock_rcon):
        """Map muvaffaqiyatli o'zgarishi kerak"""
        mock_rcon.return_value.change_map.return_value = 'Map changed'

        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            f'/api/servers/{self.server.id}/map/',
            {'map': 'bhop_arcane'},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['map'], 'bhop_arcane')
        mock_rcon.return_value.change_map.assert_called_once_with('bhop_arcane')

    @patch('servers.views.RCONService')
    def test_map_updated_in_db(self, mock_rcon):
        """Map o'zgarganda ServerConfig.current_map yangilanishi kerak"""
        mock_rcon.return_value.change_map.return_value = 'ok'

        ServerConfig.objects.create(server=self.server)

        self.client.force_authenticate(user=self.admin)
        self.client.post(
            f'/api/servers/{self.server.id}/map/',
            {'map': 'surf_utopia'},
            format='json'
        )

        # Cache muammosini oldini olish uchun yangi query
        config = ServerConfig.objects.get(server=self.server)
        self.assertEqual(config.current_map, 'surf_utopia')


# ──────────────────────────────────────────
# 4. KickPlayerView
# ──────────────────────────────────────────
class KickPlayerViewTest(BaseTestCase):

    def test_empty_steam_id_rejected(self):
        """Bo'sh steam_id 400 qaytarishi kerak"""
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            f'/api/servers/{self.server.id}/kick/',
            {'steam_id': ''},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('servers.views.RCONService')
    def test_player_kicked(self, mock_rcon):
        """Player muvaffaqiyatli kicklanishi kerak"""
        mock_rcon.return_value.kick_player.return_value = 'Player kicked'

        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            f'/api/servers/{self.server.id}/kick/',
            {'steam_id': '76561198000000001'},
            format='json'
        )


        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['kicked'], '76561198000000001')
        mock_rcon.return_value.kick_player.assert_called_once_with('76561198000000001')