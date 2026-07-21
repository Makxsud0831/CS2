from .models import SteamProfile


def save_steam_profile(backend, user, response, details=None, *args, **kwargs):
    if backend.name != 'steam':
        return

    details = details or kwargs.get('details', {}) or {}
    player = details.get('player', {}) or {}

    steam_id = player.get('steamid') or kwargs.get('uid', '')
    profile_url = player.get('profileurl', '')
    display_name = player.get('personaname', '') or details.get('username', '')
    avatar_url = player.get('avatarfull') or player.get('avatarmedium') or player.get('avatar', '')

    if not steam_id:
        return

    profile, _ = SteamProfile.objects.update_or_create(
        user=user,
        defaults={
            'steam_id64': steam_id,
            'profile_url': profile_url,
            'display_name': display_name,
            'avatar_url': avatar_url,
        }
    )

    # FACEIT: yuqori levelli o'yinchiga bir martalik VIP (login'ni bloklamasin)
    try:
        from .faceit import maybe_grant_faceit_vip
        maybe_grant_faceit_vip(profile)
    except Exception:
        pass
