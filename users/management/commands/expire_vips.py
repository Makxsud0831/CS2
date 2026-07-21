"""
Muddati tugagan VIP'larni qayta ishlaydi: skinlarini arxivlaydi (backup + WeaponPaints'dan o'chiradi).
Jadval bo'yicha ishga tushiriladi (Windows Task Scheduler / cron), masalan har soatda yoki kunda.
    .\\venv\\Scripts\\python.exe manage.py expire_vips
"""
from django.core.management.base import BaseCommand

from users.models import Subscription
from users.vip_skins import archive_loadout


class Command(BaseCommand):
    help = "Muddati tugagan VIP'larning skinlarini arxivlaydi (loadout backup + clear)."

    def handle(self, *args, **options):
        archived = 0
        # Hali arxivlanmagan obunalarni tekshiramiz
        for sub in Subscription.objects.filter(skins_archived=False).select_related('user', 'user__steam_profile'):
            if not sub.is_active():
                archive_loadout(sub.user)
                sub.skins_archived = True
                sub.save(update_fields=['skins_archived'])
                archived += 1
        # Reserved slot ro'yxatini yangilash (tugagan VIP'lar admins.json'dan chiqadi)
        if archived:
            from cs2panel.admin_sync import sync_admins
            sync_admins()
        self.stdout.write(self.style.SUCCESS(f"Arxivlangan VIP loadout: {archived}"))
