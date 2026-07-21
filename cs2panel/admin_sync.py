"""
Reserved slot / VIP priority sync:
Django aktiv VIP'larni (Subscription) CounterStrikeSharp `admins.json` ga `@css/reservation`
flagi bilan yozadi. CS2-ReservedSlots plagini connect'da shu flagni o'qib, to'la serverга
VIP'ni kiritadi. VIP tugaganda/bekor qilinganda Django faylni qayta yozadi (VIP yo'qoladi).
"""
import json

from django.conf import settings


def build_admins():
    """admins.json uchun dict: owner (root) + barcha AKTIV VIP (@css/reservation)."""
    from users.models import Subscription
    admins = {}
    owner = (settings.ADMIN_OWNER_STEAMID or '').strip()
    if owner:
        admins['Owner'] = {'identity': owner, 'flags': ['@css/root'], 'immunity': 100}

    for sub in Subscription.objects.select_related('user', 'user__steam_profile'):
        if not sub.is_active():
            continue
        sp = getattr(sub.user, 'steam_profile', None)
        if not sp or not sp.steam_id64 or sp.steam_id64 == owner:
            continue
        admins[f'vip_{sp.steam_id64}'] = {
            'identity': sp.steam_id64,
            'flags': ['@css/reservation'],
            'immunity': 10,
        }
    return admins


def write_admins_files():
    """admins.json ni har bir install'ga yozadi."""
    data = build_admins()
    for path in settings.ADMIN_CONFIG_PATHS:
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass


def reload_server_admins():
    """Ishlab turgan serverlarga css_admins_reload yuboradi (darhol qo'llanishi uchun)."""
    from servers.models import GameServer
    from servers.services import RCONService
    for s in GameServer.objects.all():
        try:
            RCONService(s).execute('css_admins_reload')
        except Exception:
            pass


def sync_admins():
    """admins.json ni yangilab, serverlarga reload yuboradi. VIP grant/revoke/expire'da chaqiriladi."""
    write_admins_files()
    reload_server_admins()
