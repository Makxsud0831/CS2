"""
VIP loadout arxivlash/tiklash:
- VIP tugaganda o'yinchining WeaponPaints skinlari backupga olinadi va o'chiriladi.
- VIP qayta olinganda backup tiklanadi.
"""
from cs2panel import skins_service
from .models import SkinBackup


def archive_loadout(user):
    """VIP tugagan o'yinchi loadoutини backupga olib, WeaponPaints'dan o'chiradi."""
    steam_id = user.get_steam_id()
    if not steam_id:
        return
    try:
        data = skins_service.export_loadout(steam_id)
        # bo'sh loadoutни ham yozamiz (keyin tiklashda muammo bo'lmasin), lekin faqat biror narsa bo'lsa
        if any(rows for rows in data.values()):
            SkinBackup.objects.update_or_create(steam_id=steam_id, defaults={'data': data})
            skins_service.clear_loadout(steam_id)
    except Exception:
        pass


def restore_loadout(user):
    """VIP qayta olingan o'yinchi backupini WeaponPaints'ga qaytaradi (bor bo'lsa)."""
    steam_id = user.get_steam_id()
    if not steam_id:
        return
    try:
        backup = SkinBackup.objects.filter(steam_id=steam_id).first()
        if backup:
            skins_service.import_loadout(steam_id, backup.data)
            backup.delete()
    except Exception:
        pass
