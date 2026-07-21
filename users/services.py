import logging
from dataclasses import dataclass
from typing import Optional

import requests
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

STEAM_API_URL = 'https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/'


@dataclass
class SteamPlayerData:
    steam_id64: str
    display_name: str
    profile_url: str
    avatar_url: str
    is_public: bool


class SteamAPIException(Exception):
    pass


class SteamAPIService:

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.STEAM_API_KEY

    def get_player_summary(self, steam_id64: str) -> dict:
        try:
            response = requests.get(
                STEAM_API_URL,
                params={
                    'key': self.api_key,
                    'steamids': steam_id64,
                },
                timeout=5,
            )
            response.raise_for_status()
        except requests.Timeout:
            raise SteamAPIException(f'Steam API timeout: {steam_id64}')
        except requests.RequestException as e:
            raise SteamAPIException(f'Steam API request failed: {e}')

        try:
            players = response.json()['response']['players']
        except (KeyError, ValueError) as e:
            raise SteamAPIException(f'Steam API invalid response: {e}')

        if not players:
            raise SteamAPIException(f'Steam player not found: {steam_id64}')

        p = players[0]
        return {
            'steam_id64': p['steamid'],
            'display_name': p.get('personaname', ''),
            'profile_url': p.get('profileurl', ''),
            'avatar_url': p.get('avatar', ''),
            'avatar_full': p.get('avatarfull', ''),
        }


class SteamProfileSyncService:

    def __init__(self, steam_api: Optional[SteamAPIService] = None):
        self.steam = steam_api or SteamAPIService()

    def sync_profile(self, user) -> bool:
        if not hasattr(user, 'steam_profile'):
            return False

        steam_profile = user.steam_profile
        try:
            data = self.steam.get_player_summary(steam_profile.steam_id64)
        except SteamAPIException:
            logger.warning('Sync failed for %s', steam_profile.steam_id64)
            return False

        steam_profile.display_name = data['display_name']
        steam_profile.profile_url = data['profile_url']
        steam_profile.last_synced = timezone.now()
        steam_profile.save(update_fields=['display_name', 'profile_url', 'last_synced'])

        logger.info('SteamProfile synced: %s', steam_profile.steam_id64)
        return True
