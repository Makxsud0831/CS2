from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.cache import cache
from unittest.mock import patch, MagicMock
from rest_framework.test import APIClient
from rest_framework import status
from .models import GameServer, ServerConfig, ServerMap

User = get_user_model()


class BaseTestCase(TestCase):
    """Barcha testlar uchun umumiy setup"""

    def setUp(self):
        cache.clear()  # testlar orasida kesh ifloslanmasligi uchun
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
# 2b. RCON buyruq whitelist/blocklist policy
# ──────────────────────────────────────────
class RCONCommandPolicyTest(BaseTestCase):

    @patch('servers.views.RCONService')
    def test_blocked_command_rejected(self, mock_rcon):
        """Bloklangan buyruq (rcon_password) 403 va RCON ga yuborilmaydi."""
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            f'/api/servers/{self.server.id}/rcon/',
            {'command': 'rcon_password hacked'}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        mock_rcon.return_value.execute.assert_not_called()

    @patch('servers.views.RCONService')
    def test_chained_injection_blocked(self, mock_rcon):
        """; orqali zanjirlangan bloklangan buyruq ham rad etiladi."""
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            f'/api/servers/{self.server.id}/rcon/',
            {'command': 'say hi; rcon_password hacked'}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        mock_rcon.return_value.execute.assert_not_called()

    @patch('servers.views.RCONService')
    def test_allowed_command_passes(self, mock_rcon):
        """Oddiy ruxsat etilgan buyruq o'tadi (blocklist faqat)."""
        mock_rcon.return_value.execute.return_value = 'ok'
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            f'/api/servers/{self.server.id}/rcon/',
            {'command': 'mp_restartgame 1'}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_rcon.return_value.execute.assert_called_once_with('mp_restartgame 1')

    def test_policy_helper_unit(self):
        from servers.services import rcon_command_allowed
        ok, _ = rcon_command_allowed('status')
        self.assertTrue(ok)
        ok, _ = rcon_command_allowed('exec autoexec')
        self.assertFalse(ok)
        ok, _ = rcon_command_allowed('say hi; quit')
        self.assertFalse(ok)


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


# ──────────────────────────────────────────
# 5. BanPlayerView
# ──────────────────────────────────────────
class BanPlayerViewTest(BaseTestCase):

    def test_regular_user_blocked(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            f'/api/servers/{self.server.id}/ban/',
            {'steam_id': 'STEAM_0:1:123'},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_empty_steam_id_rejected(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            f'/api/servers/{self.server.id}/ban/',
            {'steam_id': ''},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('servers.views.RCONService')
    def test_permanent_ban(self, mock_rcon):
        """duration=0 → permanent ban"""
        mock_rcon.return_value.ban_player.return_value = 'Player banned'

        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            f'/api/servers/{self.server.id}/ban/',
            {'steam_id': 'STEAM_0:1:123', 'duration': 0},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['banned'], 'STEAM_0:1:123')
        self.assertEqual(response.data['duration_minutes'], 0)
        mock_rcon.return_value.ban_player.assert_called_once_with('STEAM_0:1:123', 0)

    @patch('servers.views.RCONService')
    def test_timed_ban(self, mock_rcon):
        """duration=60 → 60 daqiqalik ban"""
        mock_rcon.return_value.ban_player.return_value = 'Player banned 60 min'

        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            f'/api/servers/{self.server.id}/ban/',
            {'steam_id': 'STEAM_0:1:456', 'duration': 60},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['duration_minutes'], 60)


# ──────────────────────────────────────────
# 6. SayView
# ──────────────────────────────────────────
class SayViewTest(BaseTestCase):

    def test_empty_message_rejected(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            f'/api/servers/{self.server.id}/say/',
            {'message': ''},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('servers.views.RCONService')
    def test_message_sent(self, mock_rcon):
        mock_rcon.return_value.say.return_value = ''

        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            f'/api/servers/{self.server.id}/say/',
            {'message': 'Server 5 daqiqada restart bo\'ladi!'},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_rcon.return_value.say.assert_called_once_with("Server 5 daqiqada restart bo'ladi!")


# ──────────────────────────────────────────
# 7. RestartView
# ──────────────────────────────────────────
class RestartViewTest(BaseTestCase):

    def test_regular_user_blocked(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(f'/api/servers/{self.server.id}/restart/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch('servers.views.RCONService')
    def test_server_restarted(self, mock_rcon):
        mock_rcon.return_value.restart_server.return_value = ''

        self.client.force_authenticate(user=self.admin)
        response = self.client.post(f'/api/servers/{self.server.id}/restart/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_rcon.return_value.restart_server.assert_called_once()


# ──────────────────────────────────────────
# 8. PlayersWithIDsView
# ──────────────────────────────────────────
class PlayersWithIDsViewTest(BaseTestCase):

    @patch('servers.views.RCONService')
    def test_returns_players(self, mock_rcon):
        mock_rcon.return_value.get_players_with_ids.return_value = [
            {'slot': '0', 'userid': '2', 'name': 'TestPlayer'},
        ]

        self.client.force_authenticate(user=self.user)
        response = self.client.get(f'/api/servers/{self.server.id}/players/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['players'][0]['name'], 'TestPlayer')
        self.assertEqual(response.data['players'][0]['userid'], '2')

    @patch('servers.views.RCONService')
    def test_empty_server(self, mock_rcon):
        mock_rcon.return_value.get_players_with_ids.return_value = []

        self.client.force_authenticate(user=self.user)
        response = self.client.get(f'/api/servers/{self.server.id}/players/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 0)


# ──────────────────────────────────────────
# 9. RCONService unit tests
# ──────────────────────────────────────────
class RCONServiceParseTest(TestCase):
    """RCONService.get_players_with_ids() parse logikasini test qiladi"""

    def setUp(self):
        self.server = GameServer(
            name='Test', ip='127.0.0.1', port=27015, rcon_password='x'
        )

    @patch('servers.services.Client')
    def test_parse_players_from_users(self, mock_client):
        """RCON 'users' chiqishidan o'yinchilar to'g'ri parse qilinishi kerak"""
        users_output = (
            '<slot:userid:"name">\n'
            '0:2:"MaxZ"\n'
            '1:3:"AnotherPlayer"\n'
            '2 users\n'
        )
        mock_client.return_value.__enter__ = lambda s: mock_client.return_value
        mock_client.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.return_value.run.return_value = users_output

        from .services import RCONService
        rcon = RCONService(self.server)
        players = rcon.get_players_with_ids()

        self.assertEqual(len(players), 2)
        self.assertEqual(players[0]['name'], 'MaxZ')
        self.assertEqual(players[0]['userid'], '2')
        self.assertEqual(players[1]['name'], 'AnotherPlayer')


# ──────────────────────────────────────────
# 10. Map Pool
# ──────────────────────────────────────────
class MapPoolTest(BaseTestCase):

    def setUp(self):
        super().setUp()
        self.map_easy = ServerMap.objects.create(
            server=self.server, name='bhop_easy', map_type='bhop', tier=1,
        )
        self.map_hard = ServerMap.objects.create(
            server=self.server, name='bhop_hell', map_type='bhop', tier=6,
        )
        self.map_surf = ServerMap.objects.create(
            server=self.server, name='surf_utopia', map_type='surf', tier=2,
            is_active=False,
        )

    def test_list_all_maps(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(f'/api/servers/{self.server.id}/maps/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3)

    def test_filter_by_type(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(f'/api/servers/{self.server.id}/maps/?type=surf')
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'surf_utopia')

    def test_filter_by_tier(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(f'/api/servers/{self.server.id}/maps/?tier=6')
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'bhop_hell')

    def test_filter_active_only(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(f'/api/servers/{self.server.id}/maps/?active=true')
        self.assertEqual(len(response.data), 2)

    def test_tier_display(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(f'/api/servers/{self.server.id}/maps/?tier=6')
        self.assertEqual(response.data[0]['tier_display'], 'Insane')

    def test_regular_user_cannot_create(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            f'/api/servers/{self.server.id}/maps/',
            {'name': 'bhop_new', 'map_type': 'bhop', 'tier': 3},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_create(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            f'/api/servers/{self.server.id}/maps/',
            {'name': 'kz_castle', 'map_type': 'kz', 'tier': 4, 'server': self.server.id},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            ServerMap.objects.filter(server=self.server, name='kz_castle').exists()
        )

    def test_invalid_tier_rejected(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            f'/api/servers/{self.server.id}/maps/',
            {'name': 'bhop_x', 'map_type': 'bhop', 'tier': 99, 'server': self.server.id},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_admin_can_update_tier(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.patch(
            f'/api/servers/{self.server.id}/maps/{self.map_easy.id}/',
            {'tier': 2},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.map_easy.refresh_from_db()
        self.assertEqual(self.map_easy.tier, 2)

    def test_admin_can_delete_map(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.delete(
            f'/api/servers/{self.server.id}/maps/{self.map_surf.id}/'
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(ServerMap.objects.filter(id=self.map_surf.id).exists())


# ──────────────────────────────────────────
# 11. SetCurrentMapView
# ──────────────────────────────────────────
class SetCurrentMapTest(BaseTestCase):

    def setUp(self):
        super().setUp()
        self.map1 = ServerMap.objects.create(
            server=self.server, name='bhop_arcane', map_type='bhop', tier=3,
            is_current=True,
        )
        self.map2 = ServerMap.objects.create(
            server=self.server, name='bhop_eazy', map_type='bhop', tier=1,
        )
        self.map_ws = ServerMap.objects.create(
            server=self.server, name='surf_kitsune', map_type='surf', tier=2,
            workshop_id='3070321829',
        )
        self.inactive_map = ServerMap.objects.create(
            server=self.server, name='bhop_old', map_type='bhop',
            is_active=False,
        )

    @patch('servers.views.RCONService')
    def test_set_map_via_changelevel(self, mock_rcon):
        mock_rcon.return_value.change_map.return_value = 'ok'

        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            f'/api/servers/{self.server.id}/maps/{self.map2.id}/set/'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_rcon.return_value.change_map.assert_called_once_with('bhop_eazy')

        # is_current flaglar to'g'ri almashgan
        self.map1.refresh_from_db()
        self.map2.refresh_from_db()
        self.assertFalse(self.map1.is_current)
        self.assertTrue(self.map2.is_current)

    @patch('servers.views.RCONService')
    def test_set_workshop_map(self, mock_rcon):
        mock_rcon.return_value.execute.return_value = 'ok'

        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            f'/api/servers/{self.server.id}/maps/{self.map_ws.id}/set/'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_rcon.return_value.execute.assert_called_once_with(
            'host_workshop_map 3070321829'
        )

    @patch('servers.views.RCONService')
    def test_play_count_incremented(self, mock_rcon):
        mock_rcon.return_value.change_map.return_value = 'ok'

        self.client.force_authenticate(user=self.admin)
        self.client.post(f'/api/servers/{self.server.id}/maps/{self.map2.id}/set/')

        self.map2.refresh_from_db()
        self.assertEqual(self.map2.play_count, 1)

    def test_inactive_map_rejected(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            f'/api/servers/{self.server.id}/maps/{self.inactive_map.id}/set/'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_regular_user_blocked(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            f'/api/servers/{self.server.id}/maps/{self.map2.id}/set/'
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


# ──────────────────────────────────────────
# 12. Start / Stop server (bat orqali)
# ──────────────────────────────────────────
class StartStopServerTest(BaseTestCase):

    def test_regular_user_cannot_start(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(f'/api/servers/{self.server.id}/start/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch('servers.views.ServerLauncher')
    @patch('servers.views.ServerQueryService')
    def test_start_when_offline(self, mock_qs, mock_launcher):
        mock_qs.return_value.get_info.return_value = None  # offline
        mock_launcher.return_value.start.return_value = (True, 'Server ishga tushirildi')

        self.client.force_authenticate(user=self.admin)
        response = self.client.post(f'/api/servers/{self.server.id}/start/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['started'])
        mock_launcher.return_value.start.assert_called_once()

    @patch('servers.views.ServerLauncher')
    @patch('servers.views.ServerQueryService')
    def test_start_when_already_online(self, mock_qs, mock_launcher):
        mock_qs.return_value.get_info.return_value = MagicMock()  # online

        self.client.force_authenticate(user=self.admin)
        response = self.client.post(f'/api/servers/{self.server.id}/start/')

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertFalse(response.data['started'])
        mock_launcher.return_value.start.assert_not_called()

    @patch('servers.views.ServerLauncher')
    @patch('servers.views.ServerQueryService')
    def test_start_launch_failure(self, mock_qs, mock_launcher):
        mock_qs.return_value.get_info.return_value = None
        mock_launcher.return_value.start.return_value = (False, "bat fayl topilmadi")

        self.client.force_authenticate(user=self.admin)
        response = self.client.post(f'/api/servers/{self.server.id}/start/')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data['started'])

    @patch('servers.views.RCONService')
    def test_stop_server(self, mock_rcon):
        mock_rcon.return_value.execute.return_value = ''

        self.client.force_authenticate(user=self.admin)
        response = self.client.post(f'/api/servers/{self.server.id}/stop/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['stopped'])
        mock_rcon.return_value.execute.assert_called_once_with('quit')

    def test_regular_user_cannot_stop(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(f'/api/servers/{self.server.id}/stop/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


# ──────────────────────────────────────────
# 13. ServerLauncher unit test
# ──────────────────────────────────────────
class ServerLauncherTest(TestCase):

    def test_empty_bat_path(self):
        from .services import ServerLauncher
        server = GameServer(name='x', ip='127.0.0.1', port=27015, rcon_password='x', bat_path='')
        ok, msg = ServerLauncher(server).start()
        self.assertFalse(ok)

    def test_nonexistent_bat(self):
        from .services import ServerLauncher
        server = GameServer(name='x', ip='127.0.0.1', port=27015, rcon_password='x',
                            bat_path=r'C:\yoq\bunday\fayl.bat')
        ok, msg = ServerLauncher(server).start()
        self.assertFalse(ok)

    @patch('servers.services.subprocess.Popen')
    @patch('servers.services.os.path.isfile', return_value=True)
    def test_valid_bat_launches(self, mock_isfile, mock_popen):
        from .services import ServerLauncher
        server = GameServer(name='x', ip='127.0.0.1', port=27015, rcon_password='x',
                            bat_path=r'F:\cSERVER\start.bat')
        ok, msg = ServerLauncher(server).start()
        self.assertTrue(ok)
        mock_popen.assert_called_once()