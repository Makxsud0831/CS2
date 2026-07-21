from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from unittest.mock import patch
from .models import User, Subscription, SteamProfile


class UserModelTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='pass123')

    def test_is_admin_false_by_default(self):
        self.assertFalse(self.user.is_admin())

    def test_is_admin_true_for_staff(self):
        self.user.is_staff = True
        self.assertTrue(self.user.is_admin())

    def test_is_admin_true_for_superuser(self):
        self.user.is_superuser = True
        self.assertTrue(self.user.is_admin())

    def test_is_premium_false_without_subscription(self):
        self.assertFalse(self.user.is_premium())

    def test_get_steam_id_returns_none_without_profile(self):
        self.assertIsNone(self.user.get_steam_id())

    def test_get_steam_id_returns_id_with_profile(self):
        SteamProfile.objects.create(
            user=self.user,
            steam_id64='76561198000000001',
            display_name='TestPlayer',
        )
        self.assertEqual(self.user.get_steam_id(), '76561198000000001')


class SubscriptionTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='subuser', password='pass123')

    def _make_sub(self, plan, days=30):
        return Subscription.objects.create(
            user=self.user,
            plan=plan,
            expires_at=timezone.now() + timedelta(days=days),
        )

    def test_is_active_true_when_not_expired(self):
        sub = self._make_sub(Subscription.BASIC)
        self.assertTrue(sub.is_active())

    def test_is_active_false_when_expired(self):
        sub = self._make_sub(Subscription.BASIC, days=-1)
        self.assertFalse(sub.is_active())

    def test_is_premium_true_with_active_subscription(self):
        self._make_sub(Subscription.PRO)
        self.assertTrue(self.user.is_premium())

    def test_is_premium_false_with_expired_subscription(self):
        self._make_sub(Subscription.PRO, days=-1)
        self.assertFalse(self.user.is_premium())

    def test_basic_permissions(self):
        sub = self._make_sub(Subscription.BASIC)
        perms = sub.get_permissions()
        self.assertIn('bhop', perms)
        self.assertIn('speedometer', perms)
        self.assertNotIn('noclip', perms)

    def test_pro_permissions(self):
        sub = self._make_sub(Subscription.PRO)
        perms = sub.get_permissions()
        self.assertIn('doublejump', perms)
        self.assertIn('extra_hp', perms)
        self.assertNotIn('noclip', perms)

    def test_vip_permissions(self):
        sub = self._make_sub(Subscription.VIP)
        perms = sub.get_permissions()
        self.assertIn('noclip', perms)
        self.assertIn('custom_tag', perms)

    def test_has_permission_true_when_active(self):
        sub = self._make_sub(Subscription.VIP)
        self.assertTrue(sub.has_permission('noclip'))

    def test_has_permission_false_when_expired(self):
        sub = self._make_sub(Subscription.VIP, days=-1)
        self.assertFalse(sub.has_permission('noclip'))

    def test_has_permission_false_for_wrong_plan(self):
        sub = self._make_sub(Subscription.BASIC)
        self.assertFalse(sub.has_permission('noclip'))

    def test_str(self):
        sub = self._make_sub(Subscription.PRO)
        self.assertIn('subuser', str(sub))
        self.assertIn('pro', str(sub))


class SkinAccessTest(TestCase):
    """Skin tanlash huquqlari: bepul = default pichoq; skinli = Pro/VIP.
    Backendda tekshiriladi (frontend so'rovni soxtalashtirsa ham o'tmaydi)."""

    STEAM = '76561198000000050'
    KNIFE = {'weapon_name': 'weapon_karambit', 'defindex': 507, 'display_name': 'Karambit'}

    def setUp(self):
        self.free = User.objects.create_user(username='freeuser', password='p')
        SteamProfile.objects.create(user=self.free, steam_id64=self.STEAM, display_name='Free')
        self.pro = User.objects.create_user(username='prouser', password='p')
        SteamProfile.objects.create(user=self.pro, steam_id64='76561198000000051', display_name='Pro')
        Subscription.objects.create(user=self.pro, plan=Subscription.PRO,
                                    expires_at=timezone.now() + timedelta(days=30))

    # --- BEPUL: default pichoq ---
    @patch('cs2panel.views.skins_service')
    def test_free_user_saves_default_knife(self, ss):
        ss.knife_model.return_value = self.KNIFE
        self.client.force_login(self.free)
        resp = self.client.post('/skins/save-basic/', {'weapon_name': 'weapon_karambit'})
        self.assertEqual(resp.status_code, 200)
        # paint=0 va seed=0 MAJBURAN, defindex server tomondan
        ss.set_knife.assert_called_once_with(self.STEAM, 'weapon_karambit', 507, 0, 0)

    @patch('cs2panel.views.skins_service')
    def test_basic_ignores_injected_paint(self, ss):
        """Qitmir user paint_id yuborsa ham — backend 0 majburlaydi."""
        ss.knife_model.return_value = self.KNIFE
        self.client.force_login(self.free)
        resp = self.client.post('/skins/save-basic/',
                                {'weapon_name': 'weapon_karambit', 'paint_id': '44', 'seed': '661'})
        self.assertEqual(resp.status_code, 200)
        ss.set_knife.assert_called_once_with(self.STEAM, 'weapon_karambit', 507, 0, 0)

    @patch('cs2panel.views.skins_service')
    def test_basic_invalid_knife_rejected(self, ss):
        """Haqiqiy pichoq bo'lmagan weapon_name rad etiladi (validatsiya)."""
        ss.knife_model.return_value = None
        self.client.force_login(self.free)
        resp = self.client.post('/skins/save-basic/', {'weapon_name': 'weapon_ak47'})
        self.assertEqual(resp.status_code, 400)
        ss.set_knife.assert_not_called()

    def test_anonymous_cannot_save_basic(self):
        resp = self.client.post('/skins/save-basic/', {'weapon_name': 'weapon_karambit'})
        self.assertEqual(resp.status_code, 403)

    # --- SKINLI: faqat Pro/VIP ---
    @patch('cs2panel.views.skins_service')
    def test_free_user_blocked_from_paint(self, ss):
        self.client.force_login(self.free)
        resp = self.client.post('/skins/save-all/', '{}', content_type='application/json')
        self.assertEqual(resp.status_code, 403)
        ss.set_skin.assert_not_called()

    @patch('cs2panel.views.skins_service')
    def test_pro_user_allowed_to_paint(self, ss):
        self.client.force_login(self.pro)
        resp = self.client.post('/skins/save-all/', '{}', content_type='application/json')
        self.assertEqual(resp.status_code, 200)

    # --- Sahifa render (template xatosiz) ---
    def _stub(self, ss):
        ss.load_knives.return_value = []
        ss.get_player_skins.return_value = {}
        ss.get_player_seeds.return_value = {}
        ss.get_player_knife.return_value = None
        ss.get_player_gloves.return_value = None
        ss.load_weapons.return_value = []
        ss.load_gloves.return_value = []
        ss.load_agents.return_value = []
        ss.get_player_agents.return_value = {}
        ss.agent_info.return_value = None
        ss.default_knife_image.return_value = ''

    @patch('cs2panel.views.skins_service')
    def test_free_user_page_shows_basic_and_upsell(self, ss):
        self._stub(ss)
        self.client.force_login(self.free)
        resp = self.client.get('/skins/', HTTP_HOST='localhost')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Default pichoq')   # basic bo'lim
        self.assertContains(resp, 'save-basic')        # basic save endpoint
        self.assertContains(resp, 'Pro')               # upsell

    @patch('cs2panel.views.skins_service')
    def test_pro_user_page_shows_full_grid(self, ss):
        self._stub(ss)
        self.client.force_login(self.pro)
        resp = self.client.get('/skins/', HTTP_HOST='localhost')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'save-all')          # full grid save
        self.assertContains(resp, 'Default pichoq')    # basic ham ko'rinadi


class SteamProfileTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='steamuser', password='pass123')
        self.profile = SteamProfile.objects.create(
            user=self.user,
            steam_id64='76561198000000099',
            display_name='SteamPlayer',
            profile_url='https://steamcommunity.com/id/steamplayer',
        )

    def test_str(self):
        self.assertIn('SteamPlayer', str(self.profile))
        self.assertIn('76561198000000099', str(self.profile))

    def test_sync_updates_last_synced(self):
        self.assertIsNone(self.profile.last_synced)
        self.profile.sync()
        self.assertIsNotNone(self.profile.last_synced)

    def test_steam_id64_is_unique(self):
        other_user = User.objects.create_user(username='other', password='pass')
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            SteamProfile.objects.create(
                user=other_user,
                steam_id64='76561198000000099',
            )
