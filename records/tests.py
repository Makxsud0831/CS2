from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from servers.models import GameServer, ServerMap
from .models import PlayerRecord, RecordHistory, MapCompletion
from .services import RecordService, RunResult

User = get_user_model()


class BaseRecordTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='player1', password='pass123')
        self.user2 = User.objects.create_user(username='player2', password='pass123')

        self.server = GameServer.objects.create(
            name='Bhop Server', ip='10.0.0.1', port=27015, rcon_password='x'
        )
        self.map = ServerMap.objects.create(
            server=self.server,
            name='bhop_arcane',
            map_type='bhop',
        )

    def _run(self, user=None, time_ms=10000.0, style='normal', **kwargs):
        return RunResult(
            user_id=(user or self.user).pk,
            map_id=self.map.pk,
            style=style,
            time_ms=time_ms,
            **kwargs,
        )


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# RecordService
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
class RecordServiceTest(BaseRecordTestCase):

    def test_first_run_creates_record(self):
        result = RecordService().submit_run(self._run(time_ms=10000))
        self.assertTrue(result.is_pb)
        self.assertEqual(PlayerRecord.objects.count(), 1)

    def test_first_run_no_history(self):
        RecordService().submit_run(self._run(time_ms=10000))
        self.assertEqual(RecordHistory.objects.count(), 0)

    def test_faster_run_updates_pb(self):
        RecordService().submit_run(self._run(time_ms=10000))
        result = RecordService().submit_run(self._run(time_ms=9000))
        self.assertTrue(result.is_pb)
        self.assertEqual(PlayerRecord.objects.count(), 1)
        self.assertEqual(PlayerRecord.objects.first().time_ms, 9000)

    def test_faster_run_saves_history(self):
        RecordService().submit_run(self._run(time_ms=10000))
        RecordService().submit_run(self._run(time_ms=9000))
        self.assertEqual(RecordHistory.objects.count(), 1)
        self.assertEqual(RecordHistory.objects.first().time_ms, 10000)

    def test_improvement_ms_correct(self):
        RecordService().submit_run(self._run(time_ms=10000))
        result = RecordService().submit_run(self._run(time_ms=9000))
        self.assertAlmostEqual(result.improvement_ms, 1000.0)

    def test_slower_run_not_pb(self):
        RecordService().submit_run(self._run(time_ms=9000))
        result = RecordService().submit_run(self._run(time_ms=10000))
        self.assertFalse(result.is_pb)
        self.assertEqual(PlayerRecord.objects.first().time_ms, 9000)

    def test_slower_run_no_history(self):
        RecordService().submit_run(self._run(time_ms=9000))
        RecordService().submit_run(self._run(time_ms=10000))
        self.assertEqual(RecordHistory.objects.count(), 0)

    def test_rank_1_is_wr(self):
        result = RecordService().submit_run(self._run(time_ms=9000))
        self.assertTrue(result.is_wr)
        self.assertEqual(result.rank, 1)

    def test_rank_2_not_wr(self):
        RecordService().submit_run(self._run(user=self.user, time_ms=8000))
        result = RecordService().submit_run(self._run(user=self.user2, time_ms=9000))
        self.assertFalse(result.is_wr)
        self.assertEqual(result.rank, 2)

    def test_style_separate_records(self):
        RecordService().submit_run(self._run(style='normal', time_ms=10000))
        RecordService().submit_run(self._run(style='sw', time_ms=12000))
        self.assertEqual(PlayerRecord.objects.count(), 2)

    def test_completion_created_on_run(self):
        RecordService().submit_run(self._run())
        self.assertEqual(MapCompletion.objects.count(), 1)

    def test_completion_count_increments(self):
        RecordService().submit_run(self._run(time_ms=10000))
        RecordService().submit_run(self._run(time_ms=9000))
        self.assertEqual(MapCompletion.objects.first().count, 2)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# submit_run API
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
class SubmitRunViewTest(BaseRecordTestCase):

    def test_unauthenticated_blocked(self):
        response = self.client.post('/api/records/submit/', {'map_id': self.map.pk, 'time_ms': 9000})
        self.assertIn(response.status_code, [401, 403])

    def test_missing_fields_rejected(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post('/api/records/submit/', {}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_invalid_map_rejected(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post('/api/records/submit/', {'map_id': 9999, 'time_ms': 9000}, format='json')
        self.assertEqual(response.status_code, 404)

    def test_negative_time_rejected(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post('/api/records/submit/', {'map_id': self.map.pk, 'time_ms': -100}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_invalid_style_rejected(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post('/api/records/submit/', {
            'map_id': self.map.pk, 'time_ms': 9000, 'style': 'invalid'
        }, format='json')
        self.assertEqual(response.status_code, 400)

    def test_valid_run_accepted(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post('/api/records/submit/', {
            'map_id': self.map.pk, 'time_ms': 9000, 'style': 'normal',
            'jumps': 120, 'strafes': 80, 'sync': 87.5,
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['is_pb'])
        self.assertIn('record', response.data)

    def test_pb_improves_response(self):
        self.client.force_authenticate(user=self.user)
        self.client.post('/api/records/submit/', {'map_id': self.map.pk, 'time_ms': 10000}, format='json')
        response = self.client.post('/api/records/submit/', {'map_id': self.map.pk, 'time_ms': 9000}, format='json')
        self.assertTrue(response.data['is_pb'])
        self.assertAlmostEqual(response.data['improvement_ms'], 1000.0)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Leaderboard API
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
class LeaderboardViewTest(BaseRecordTestCase):

    def test_leaderboard_ordered_by_time(self):
        RecordService().submit_run(self._run(user=self.user, time_ms=9000))
        RecordService().submit_run(self._run(user=self.user2, time_ms=8000))

        self.client.force_authenticate(user=self.user)
        response = self.client.get(f'/api/records/maps/{self.map.pk}/leaderboard/')

        self.assertEqual(response.status_code, 200)
        times = [r['time_ms'] for r in response.data]
        self.assertEqual(times, sorted(times))

    def test_leaderboard_filters_by_style(self):
        RecordService().submit_run(self._run(user=self.user, time_ms=9000, style='normal'))
        RecordService().submit_run(self._run(user=self.user2, time_ms=8000, style='sw'))

        self.client.force_authenticate(user=self.user)
        response = self.client.get(f'/api/records/maps/{self.map.pk}/leaderboard/?style=sw')

        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['time_ms'], 8000)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# My records API
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
class MyRecordsViewTest(BaseRecordTestCase):

    def test_returns_only_own_records(self):
        RecordService().submit_run(self._run(user=self.user, time_ms=9000))
        RecordService().submit_run(self._run(user=self.user2, time_ms=8000))

        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/records/me/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['username'], 'player1')


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Player Search
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
from unittest.mock import patch, MagicMock
from users.models import SteamProfile


class PlayerSearchTest(BaseRecordTestCase):

    def test_short_query_rejected(self):
        response = self.client.get('/api/records/search/?q=a')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_empty_query_rejected(self):
        response = self.client.get('/api/records/search/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('records.views.SharpTimerStatsService')
    def test_finds_panel_user_by_username(self, mock_st):
        mock_st.return_value.search_players.return_value = []

        response = self.client.get('/api/records/search/?q=player1')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        usernames = [u['username'] for u in response.data['panel_users']]
        self.assertIn('player1', usernames)

    @patch('records.views.SharpTimerStatsService')
    def test_finds_panel_user_by_steam_name(self, mock_st):
        mock_st.return_value.search_players.return_value = []
        SteamProfile.objects.create(
            user=self.user, steam_id64='76561199538815857', display_name='MaxZ'
        )

        response = self.client.get('/api/records/search/?q=maxz')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['panel_users']), 1)
        self.assertEqual(response.data['panel_users'][0]['display_name'], 'MaxZ')

    @patch('records.views.SharpTimerStatsService')
    def test_finds_panel_user_by_steam_id(self, mock_st):
        mock_st.return_value.search_players.return_value = []
        SteamProfile.objects.create(
            user=self.user, steam_id64='76561199538815857', display_name='MaxZ'
        )

        response = self.client.get('/api/records/search/?q=7656119953')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['panel_users']), 1)

    @patch('records.views.SharpTimerStatsService')
    def test_st_players_included(self, mock_st):
        mock_player = MagicMock()
        mock_player.SteamID = '76561199538815857'
        mock_player.PlayerName = 'MaxZ'
        mock_player.GlobalPoints = 1500
        mock_player.TimesConnected = 10
        mock_player.LastConnected = 1750000000
        mock_player.HideStats = False
        mock_st.return_value.search_players.return_value = [mock_player]

        response = self.client.get('/api/records/search/?q=maxz')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['st_players']), 1)
        self.assertEqual(response.data['st_players'][0]['PlayerName'], 'MaxZ')

    @patch('records.views.SharpTimerStatsService')
    def test_no_results(self, mock_st):
        mock_st.return_value.search_players.return_value = []

        response = self.client.get('/api/records/search/?q=yoqodam')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['panel_users'], [])
        self.assertEqual(response.data['st_players'], [])


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# API Token auth (CS2 server â†’ Django)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
from rest_framework.authtoken.models import Token


class TokenAuthTest(BaseRecordTestCase):

    def setUp(self):
        super().setUp()
        self.bot = User.objects.create_user(username='cs2bot')
        self.bot.set_unusable_password()
        self.bot.save()
        self.token = Token.objects.create(user=self.bot)

    def test_submit_with_valid_token(self):
        """CS2 server token bilan run yubora olishi kerak"""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        response = self.client.post('/api/records/submit/', {
            'map_id': self.map.pk,
            'time_ms': 95000,
            'style': 'normal',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_pb'])

    def test_submit_with_invalid_token(self):
        self.client.credentials(HTTP_AUTHORIZATION='Token notogri_token_123')
        response = self.client.post('/api/records/submit/', {
            'map_id': self.map.pk,
            'time_ms': 95000,
        }, format='json')
        self.assertIn(response.status_code, [401, 403])

    def test_submit_without_token(self):
        response = self.client.post('/api/records/submit/', {
            'map_id': self.map.pk,
            'time_ms': 95000,
        }, format='json')
        self.assertIn(response.status_code, [401, 403])

    def test_obtain_token_endpoint(self):
        """Username/password bilan token olish mumkin"""
        response = self.client.post('/api/auth/token/', {
            'username': 'player1',
            'password': 'pass123',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('token', response.data)

    def test_obtain_token_wrong_password(self):
        response = self.client.post('/api/auth/token/', {
            'username': 'player1',
            'password': 'notogri',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


from django.core.cache import cache as _cache


class TokenRateLimitTest(BaseRecordTestCase):
    """Token endpoint IP bo'yicha 5/daqiqa — brute-force himoyasi."""

    def setUp(self):
        super().setUp()
        _cache.clear()

    def test_sixth_attempt_rate_limited(self):
        ip = '203.0.113.50'  # boshqa testlarga ta'sir qilmaslik uchun alohida IP
        codes = []
        for _ in range(6):
            r = self.client.post('/api/auth/token/', {
                'username': 'player1', 'password': 'notogri',
            }, format='json', REMOTE_ADDR=ip)
            codes.append(r.status_code)
        self.assertNotIn(429, codes[:5])   # birinchi 5 ta o'tadi (limitга tegmaydi)
        self.assertEqual(codes[5], 429)    # 6-chisi bloklanadi

    def test_argon2_is_default_hasher(self):
        u = User.objects.create_user(username='hashcheck', password='Secret#123')
        self.assertTrue(u.password.startswith('argon2'))



# ──────────────────────────────────────────
# CheckpointStat (cp/tp) endpoint
# ──────────────────────────────────────────
from records.models import CheckpointStat as _CPStat


class CheckpointSubmitTest(BaseRecordTestCase):

    def setUp(self):
        super().setUp()
        from rest_framework.authtoken.models import Token as _Tok
        self.bot = User.objects.create_user(username='cpbot')
        self.token = _Tok.objects.create(user=self.bot)

    def test_submit_creates_stat(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        resp = self.client.post('/api/records/checkpoints/', {
            'steam_id': '76561199538815857', 'map_name': 'kz_phamous',
            'style': 0, 'cp_count': 5, 'tp_count': 3,
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(_CPStat.objects.filter(steam_id='76561199538815857', map_name='kz_phamous').exists())

    def test_submit_upserts(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        for cp in (2, 7):
            self.client.post('/api/records/checkpoints/', {
                'steam_id': '111', 'map_name': 'kz_x', 'style': 0,
                'cp_count': cp, 'tp_count': 1,
            }, format='json')
        self.assertEqual(_CPStat.objects.filter(steam_id='111', map_name='kz_x').count(), 1)
        self.assertEqual(_CPStat.objects.get(steam_id='111', map_name='kz_x').cp_count, 7)

    def test_missing_fields_rejected(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        resp = self.client.post('/api/records/checkpoints/', {'cp_count': 1}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_no_auth_blocked(self):
        resp = self.client.post('/api/records/checkpoints/', {
            'steam_id': '1', 'map_name': 'kz_x',
        }, format='json')
        self.assertIn(resp.status_code, [401, 403])


from django.test import override_settings


class CheckpointTrustedIPTest(BaseRecordTestCase):
    """submit_checkpoints faqat ishonchli server IP'sidan (sozlanganda)."""

    def setUp(self):
        super().setUp()
        from rest_framework.authtoken.models import Token as _Tok
        self.bot = User.objects.create_user(username='cpbot2')
        self.token = _Tok.objects.create(user=self.bot)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')

    @override_settings(TRUSTED_SERVER_IPS=['10.0.0.5'])
    def test_untrusted_ip_blocked(self):
        resp = self.client.post('/api/records/checkpoints/', {
            'steam_id': '1', 'map_name': 'kz_x', 'cp_count': 1,
        }, format='json', REMOTE_ADDR='8.8.8.8')
        self.assertEqual(resp.status_code, 403)

    @override_settings(TRUSTED_SERVER_IPS=['10.0.0.5'])
    def test_trusted_ip_allowed(self):
        resp = self.client.post('/api/records/checkpoints/', {
            'steam_id': '1', 'map_name': 'kz_x', 'cp_count': 1,
        }, format='json', REMOTE_ADDR='10.0.0.5')
        self.assertEqual(resp.status_code, 200)

    @override_settings(TRUSTED_SERVER_IPS=[])
    def test_empty_list_allows_all(self):
        resp = self.client.post('/api/records/checkpoints/', {
            'steam_id': '1', 'map_name': 'kz_x', 'cp_count': 1,
        }, format='json', REMOTE_ADDR='8.8.8.8')
        self.assertEqual(resp.status_code, 200)
