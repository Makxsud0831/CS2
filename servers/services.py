from rcon.source import Client
import a2s


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

    def change_map(self, map_name: str):
        return self.execute(f"changelevel {map_name}")

    def kick_player(self, steam_id: str):
        return self.execute(f"kickid {steam_id}")

    def get_status(self):
        return self.execute("status")

    def say(self, message: str):
        return self.execute(f'say [Panel] {message}')


class ServerQueryService:
    def __init__(self, server):
        self.server = server

    def _addr(self):
        return (self.server.ip, self.server.port)

    def get_info(self):
        try:
            return a2s.info(self._addr())
        except Exception:
            return None

    def get_players(self):
        try:
            return a2s.players(self._addr())
        except Exception:
            return []
