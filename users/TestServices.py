from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from unittest.mock import patch, MagicMock
from .models import SteamProfile
from .services import SteamAPIService, SteamProfileSyncService, SteamAPIException

User = get_user_model()


class BaseSteamTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.steam_profile = SteamProfile.objects.create(
            user=self.user,
            steam_id64='76561198000000001',
            profile_url='https://steamcommunity.com/id/old/',
            display_name='OldName',
        )


# ──────────────────────────────────────────
# 1. SteamAPIService
# ──────────────────────────────────────────
class SteamAPIServiceTest(TestCase):

    @patch('users.services.requests.get')
    def test_returns_player_data(self, mock_get):
        """API muvaffaqiyatli javob qaytarsa to'g'ri parse qilinishi kerak"""
        mock_get.return_value.json.return_value = {
            'response': {
                'players': [{
                    'steamid': '76561198000000001',
                    'personaname': 'xX_Player_Xx',
                    'profileurl': 'https://steamcommunity.com/id/player/',
                    'avatar': 'https://cdn.steam.com/avatar.jpg',
                    'avatarfull': 'https://cdn.steam.com/avatar_full.jpg',
                }]
            }
        }
        mock_get.return_value.raise_for_status = MagicMock()

        service = SteamAPIService(api_key='fake_key')
        result = service.get_player_summary('76561198000000001')

        self.assertEqual(result['display_name'], 'xX_Player_Xx')
        self.assertEqual(result['steam_id64'], '76561198000000001')
        self.assertIn('avatar_full', result)

    @patch('users.services.requests.get')
    def test_empty_players_raises_exception(self, mock_get):
        """players bo'sh bo'lsa SteamAPIException ko'tarilishi kerak"""
        mock_get.return_value.json.return_value = {
            'response': {'players': []}
        }
        mock_get.return_value.raise_for_status = MagicMock()

        service = SteamAPIService(api_key='fake_key')

        with self.assertRaises(SteamAPIException):
            service.get_player_summary('00000000000000000')

    @patch('users.services.requests.get')
    def test_timeout_raises_exception(self, mock_get):
        """Timeout bo'lsa SteamAPIException ko'tarilishi kerak"""
        import requests as req
        mock_get.side_effect = req.Timeout()

        service = SteamAPIService(api_key='fake_key')

        with self.assertRaises(SteamAPIException) as ctx:
            service.get_player_summary('76561198000000001')

        self.assertIn('timeout', str(ctx.exception).lower())

    @patch('users.services.requests.get')
    def test_request_exception_raises(self, mock_get):
        """Network xatolik bo'lsa SteamAPIException ko'tarilishi kerak"""
        import requests as req
        mock_get.side_effect = req.RequestException('connection error')

        service = SteamAPIService(api_key='fake_key')

        with self.assertRaises(SteamAPIException):
            service.get_player_summary('76561198000000001')


# ──────────────────────────────────────────
# 2. SteamProfileSyncService
# ──────────────────────────────────────────
class SteamProfileSyncServiceTest(BaseSteamTestCase):

    def _make_sync_service(self, return_data=None, raise_exc=None):
        """Mock SteamAPIService bilan SteamProfileSyncService qaytaradi"""
        mock_api = MagicMock(spec=SteamAPIService)

        if raise_exc:
            mock_api.get_player_summary.side_effect = raise_exc
        else:
            mock_api.get_player_summary.return_value = return_data or {
                'steam_id64': '76561198000000001',
                'display_name': 'NewName',
                'profile_url': 'https://steamcommunity.com/id/new/',
                'avatar_url': 'https://cdn.steam.com/avatar.jpg',
                'avatar_full': 'https://cdn.steam.com/avatar_full.jpg',
            }

        return SteamProfileSyncService(steam_api=mock_api)

    def test_sync_updates_display_name(self):
        """sync_profile display_name ni yangilashi kerak"""
        sync = self._make_sync_service()
        result = sync.sync_profile(self.user)

        self.assertTrue(result)
        self.steam_profile.refresh_from_db()
        self.assertEqual(self.steam_profile.display_name, 'NewName')

    def test_sync_updates_profile_url(self):
        """sync_profile profile_url ni yangilashi kerak"""
        sync = self._make_sync_service()
        sync.sync_profile(self.user)

        self.steam_profile.refresh_from_db()
        self.assertEqual(
            self.steam_profile.profile_url,
            'https://steamcommunity.com/id/new/'
        )

    def test_sync_updates_last_synced(self):
        """sync_profile last_synced ni yangilashi kerak"""
        self.assertIsNone(self.steam_profile.last_synced)

        sync = self._make_sync_service()
        sync.sync_profile(self.user)

        self.steam_profile.refresh_from_db()
        self.assertIsNotNone(self.steam_profile.last_synced)

    def test_sync_returns_false_without_steam_profile(self):
        """steam_profile yo'q userni sync qilsa False qaytarishi kerak"""
        user2 = User.objects.create_user(
            username='nosteam',
            password='pass123'
        )
        sync = self._make_sync_service()
        result = sync.sync_profile(user2)

        self.assertFalse(result)

    def test_sync_returns_false_on_api_error(self):
        """API xatolik qaytarsa False qaytarishi kerak (exception emas)"""
        sync = self._make_sync_service(
            raise_exc=SteamAPIException('API down')
        )
        result = sync.sync_profile(self.user)

        self.assertFalse(result)

    def test_sync_does_not_change_steam_id(self):
        """sync_profile steam_id64 ni o'zgartirmasligi kerak"""
        sync = self._make_sync_service()
        sync.sync_profile(self.user)

        self.steam_profile.refresh_from_db()
        self.assertEqual(self.steam_profile.steam_id64, '76561198000000001')

    def test_api_called_with_correct_steam_id(self):
        """get_player_summary to'g'ri steam_id bilan chaqirilishi kerak"""
        mock_api = MagicMock(spec=SteamAPIService)
        mock_api.get_player_summary.return_value = {
            'steam_id64': '76561198000000001',
            'display_name': 'X',
            'profile_url': '',
            'avatar_url': '',
            'avatar_full': '',
        }

        sync = SteamProfileSyncService(steam_api=mock_api)
        sync.sync_profile(self.user)

        mock_api.get_player_summary.assert_called_once_with('76561198000000001')