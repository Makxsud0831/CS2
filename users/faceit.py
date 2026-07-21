"""
FACEIT integratsiyasi: o'yinchining FACEIT levelini SteamID64 orqali oladi va
yuqori levelli (default 10) o'yinchilarga BIR MARTALIK VIP beradi.
"""
import requests
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

FACEIT_PLAYERS_URL = "https://open.faceit.com/data/v4/players"


def get_faceit_level(steam_id64):
    """SteamID64 bo'yicha FACEIT CS2 levelini qaytaradi (1-10) yoki None.
    Xato/topilmasa None (login bloklanmasligi uchun)."""
    if not settings.FACEIT_API_KEY or not steam_id64:
        return None
    try:
        resp = requests.get(
            FACEIT_PLAYERS_URL,
            params={"game": "cs2", "game_player_id": str(steam_id64)},
            headers={"Authorization": f"Bearer {settings.FACEIT_API_KEY}"},
            timeout=4,
        )
        if resp.status_code != 200:
            return None
        games = resp.json().get("games", {}) or {}
        g = games.get("cs2") or games.get("csgo") or {}
        level = g.get("skill_level")
        return int(level) if level is not None else None
    except Exception:
        return None


def maybe_grant_faceit_vip(profile):
    """Profil uchun FACEIT VIP berishni tekshiradi (bir martalik).
    - Allaqachon berilgan bo'lsa hech narsa qilmaydi (qayta loginda qayta bermaydi).
    - Mavjud (sotib olingan) uzunroq VIPni QISQARTIRMAYDI."""
    if profile.faceit_vip_granted or not settings.FACEIT_API_KEY:
        return

    level = get_faceit_level(profile.steam_id64)
    if level is None:
        return  # API ishlamadi / topilmadi — keyingi loginda qayta urinadi

    profile.faceit_level = level

    if level >= settings.FACEIT_VIP_LEVEL:
        from .models import Subscription
        new_exp = timezone.now() + timedelta(days=settings.FACEIT_VIP_DAYS)
        sub, created = Subscription.objects.get_or_create(
            user=profile.user,
            defaults={"plan": settings.FACEIT_VIP_PLAN, "expires_at": new_exp,
                      "skins_archived": False},
        )
        # faqat ko'proq vaqt bersa yangilaymiz (paid VIPni qisqartirmaymiz)
        if not created and sub.expires_at < new_exp:
            sub.plan = settings.FACEIT_VIP_PLAN
            sub.expires_at = new_exp
            sub.skins_archived = False
            sub.save()
        profile.faceit_vip_granted = True  # bir martalik — boshqa bermaymiz

        # arxivlangan skinlarni tiklash (oldin VIP bo'lib tugagan bo'lsa)
        from .vip_skins import restore_loadout
        restore_loadout(profile.user)
        # Reserved slot: admins.json sync
        try:
            from cs2panel.admin_sync import sync_admins
            sync_admins()
        except Exception:
            pass

    profile.save(update_fields=["faceit_level", "faceit_vip_granted"])
