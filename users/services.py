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
    """Steam API xatosi"""
    pass


class SteamAPIService:
    """
    Steam Web API bilan ishlaydi.
    STEAM_API_KEY settings da bo'lishi kerak.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.STEAM_API_KEY

    def get_player(self, steam_id64: str) -> Optional[SteamPlayerData]:
        """
        Bitta player ma'lumotini Steam API dan oladi.
        Topilmasa None qaytaradi, xato bo'lsa SteamAPIException tashlaydi.
        """
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
            logger.warning('Steam player not found: %s', steam_id64)
            return None

        p = players[0]
        return SteamPlayerData(
            steam_id64=p['steamid'],
            display_name=p.get('personaname', ''),
            profile_url=p.get('profileurl', ''),
            avatar_url=p.get('avatarfull', p.get('avatar', '')),
            is_public=p.get('communityvisibilitystate', 1) == 3,
        )


class SteamProfileSyncService:
    """
    SteamProfile modelini Steam API dan yangilaydi.
    """

    def __init__(self, steam_service: Optional[SteamAPIService] = None):
        self.steam = steam_service or SteamAPIService()

    def sync(self, steam_profile) -> bool:
        """
        SteamProfile instance ni yangilaydi.
        Muvaffaqiyatli bo'lsa True, topilmasa False qaytaradi.
        SteamAPIException ni yuqoriga o'tkazadi.
        """
        data = self.steam.get_player(steam_profile.steam_id64)

        if data is None:
            logger.warning(
                'Sync skipped — player not found: %s',
                steam_profile.steam_id64
            )
            return False

        steam_profile.display_name = data.display_name
        steam_profile.profile_url = data.profile_url
        steam_profile.last_synced = timezone.now()
        steam_profile.save(update_fields=['display_name', 'profile_url', 'last_synced'])

        logger.info('SteamProfile synced: %s', steam_profile.steam_id64)
        return True
