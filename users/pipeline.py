from .models import SteamProfile


def save_steam_profile(backend, user, response, *args, **kwargs):
    if backend.name == 'steam':
        steam_id = response.get('steamid')
        profile_url = response.get('profileurl', '')
        display_name = response.get('personaname', '')

        SteamProfile.objects.update_or_create(
            user=user,
            defaults={
                'steam_id64': steam_id,
                'profile_url': profile_url,
                'display_name': display_name,
            }
        )