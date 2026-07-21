import re
import os
import subprocess
from rcon.source import Client
from django.conf import settings
import a2s


def _rcon_segments(command):
    """Buyruqni ; va yangi qatorlar bo'yicha alohida buyruqlarga ajratadi
    (zanjir-injection: 'say hi; rcon_password x' ni ham tekshirish uchun)."""
    return [seg.strip() for seg in re.split(r'[;\n\r]+', command or '') if seg.strip()]


def rcon_command_allowed(command):
    """Generic RCON oynasidan kelgan buyruqni policy bo'yicha tekshiradi.
    Qaytaradi: (ruxsat: bool, sabab: str). Har bir segment (root token) tekshiriladi."""
    blocked = {c.lower() for c in settings.RCON_BLOCKED_COMMANDS}
    allowed = {c.lower() for c in settings.RCON_ALLOWED_COMMANDS}
    segments = _rcon_segments(command)
    if not segments:
        return False, "buyruq bo'sh"
    for seg in segments:
        root = seg.split()[0].lower()
        if root in blocked:
            return False, f"'{root}' bloklangan buyruq"
        if allowed and root not in allowed:
            return False, f"'{root}' ruxsat etilmagan (whitelist)"
    return True, ''


class ServerLauncher:
    def __init__(self, server):
        self.server = server

    def start(self) -> tuple[bool, str]:
        bat = (self.server.bat_path or '').strip()
        if not bat:
            return False, "bat_path o'rnatilmagan"
        if not os.path.isfile(bat):
            return False, f"bat fayl topilmadi: {bat}"
        if not bat.lower().endswith('.bat'):
            return False, "faqat .bat fayl ruxsat etiladi"

        try:
            subprocess.Popen(
                [bat],
                cwd=os.path.dirname(bat),
                creationflags=subprocess.CREATE_NEW_CONSOLE,
                close_fds=True,
            )
            return True, "Server ishga tushirildi"
        except Exception as e:
            return False, f"Ishga tushirish xatosi: {e}"


class RCONService:
    def __init__(self, server):
        self.server = server

    def execute(self, command: str) -> str:
        try:
            with Client(
                self.server.ip,
                self.server.port,
                passwd=self.server.rcon_password,
                timeout=5
            ) as client:
                return client.run(command)
        except Exception as e:
            return f"RCON xato: {e}"

    def change_map(self, map_name: str) -> str:
        m = map_name.strip()
        if m.isdigit():
            return self.execute(f"host_workshop_map {m}")
        # Nom berilgan: workshop map'ni 'changelevel <nom>' bilan yuklab BO'LMAYDI —
        # lokal fayl topilmay server idle'ga tushadi va RCON uziladi. Shu serverning
        # ServerMap'idan workshop ID topilsa, host_workshop_map ishlatamiz.
        server_map = self.server.maps.filter(name=m).first()
        if server_map and server_map.workshop_id:
            return self.execute(f"host_workshop_map {server_map.workshop_id}")
        return self.execute(f"changelevel {m}")

    def kick_player(self, steam_id: str) -> str:
        return self.execute(f"kickid {steam_id}")

    def ban_player(self, steam_id: str, duration_minutes: int = 0) -> str:
        return self.execute(f"banid {duration_minutes} {steam_id} kick")

    def unban_player(self, steam_id: str) -> str:
        return self.execute(f"removeid {steam_id}")

    def say(self, message: str) -> str:
        return self.execute(f'say [ADMIN] {message}')

    def restart_server(self) -> str:
        """Map ni qayta yuklash orqali server ni refresh qiladi."""
        return self.execute("mp_restartgame 1")

    def get_status(self) -> str:
        return self.execute("status")

    def get_players_with_ids(self) -> list[dict]:
        raw = self.execute('users')
        players = []
        for line in raw.splitlines():
            match = re.match(r'^\s*(\d+):(\d+):"(.+)"\s*$', line)
            if match:
                players.append({
                    'slot': match.group(1),
                    'userid': match.group(2),
                    'name': match.group(3),
                })
        return players

    def exec_cfg(self, cfg_name: str) -> str:
        return self.execute(f"exec {cfg_name}")


class ServerQueryService:
    def __init__(self, server):
        self.server = server

    def _addr(self):
        return (self.server.ip, self.server.port)

    def get_info(self, timeout=None):
        try:
            if timeout:
                return a2s.info(self._addr(), timeout=timeout)
            return a2s.info(self._addr())
        except Exception:
            return None

    def get_players(self):
        try:
            return a2s.players(self._addr())
        except Exception:
            return []
