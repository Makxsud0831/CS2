from django.contrib.auth import logout as auth_logout
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.response import Response

from servers.models import GameServer
from records.stats_service import SharpTimerStatsService
from . import skins_service


@method_decorator(ratelimit(key='ip', rate='5/m', method='POST', block=False), name='post')
class RateLimitedObtainAuthToken(ObtainAuthToken):
    """Token olish (username/parol) — IP bo'yicha 5/daqiqa. Brute-force himoyasi."""

    def post(self, request, *args, **kwargs):
        if getattr(request, 'limited', False):
            return Response(
                {'error': "Juda ko'p urinish. Bir daqiqadan keyin qayta urining."},
                status=429,
            )
        return super().post(request, *args, **kwargs)

LB_PAGE_SIZE = 50      # bir sahifada nechta o'yinchi
LB_MAX = 200           # leaderboardda umumiy maksimal o'yinchi (yukni kamaytirish)
CACHE_TTL = 60         # so'rov natijalari shuncha soniya keshlanadi (DB yukini kamaytiradi)


def home(request):
    """Bosh sahifa — serverlar TUR bo'yicha guruhlanadi (surf, bhop, kz, 1v1...)."""
    TYPE_ORDER = ['surf', 'bhop', 'kz', '1v1', 'aim', 'dm', 'other']
    TYPE_LABELS = {'surf': 'Surf', 'bhop': 'Bhop', 'kz': 'KZ', '1v1': '1v1',
                   'aim': 'Aim', 'dm': 'Deathmatch', 'other': 'Boshqa'}
    by_type = {}
    for s in GameServer.objects.all().order_by('port'):
        by_type.setdefault(s.server_type, []).append({
            'id': s.id,
            'name': s.name,
            'region': s.region,
            'port': s.port,
            'map_image': s.map_image,
            'current_map': s.current_map,
        })
    groups = []
    for t in TYPE_ORDER:
        if by_type.get(t):
            groups.append({'type': t, 'label': TYPE_LABELS.get(t, t), 'servers': by_type.pop(t)})
    for t, lst in by_type.items():  # ro'yxatda yo'q turlar (bo'lsa)
        groups.append({'type': t, 'label': TYPE_LABELS.get(t, t.upper()), 'servers': lst})
    return render(request, 'home.html', {'groups': groups})


def leaderboard(request):
    """Global top o'yinchilar (paginatsiya bilan, keshlanadi)."""
    rows = cache.get('lb_global')
    if rows is None:
        players = SharpTimerStatsService().get_global_top(limit=LB_MAX)
        rows = [
            {'name': p.PlayerName, 'points': p.GlobalPoints, 'connected': p.TimesConnected,
             'steam_id': p.SteamID}
            for p in players
        ]
        cache.set('lb_global', rows, CACHE_TTL)

    paginator = Paginator(rows, LB_PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get('page'))
    start = (page_obj.number - 1) * LB_PAGE_SIZE
    players = [dict(rank=start + i + 1, **r) for i, r in enumerate(page_obj.object_list)]

    return render(request, 'leaderboard.html', {'players': players, 'page_obj': page_obj})


def map_leaderboards(request):
    maps = cache.get('lb_maps')
    if maps is None:
        from records.models import STPlayerRecord
        qs = (
            STPlayerRecord.objects
            .values('MapName')
            .annotate(cnt=Count('SteamID'))
            .order_by('MapName')
        )
        maps = [{'name': m['MapName'], 'count': m['cnt']} for m in qs]
        cache.set('lb_maps', maps, 120)
    return render(request, 'map_leaderboards.html', {'maps': maps})


def map_leaderboard_detail(request, map_name):
    key = f'lb_map_{map_name}'
    entries = cache.get(key)
    if entries is None:
        entries = SharpTimerStatsService().get_map_leaderboard(map_name, style=0, limit=100)
        from records.models import CheckpointStat
        cp_map = {
            c.steam_id: (c.cp_count, c.tp_count)
            for c in CheckpointStat.objects.filter(map_name=map_name, style=0)
        }
        for e in entries:
            cp, tp = cp_map.get(e['steam_id'], (None, None))
            e['cp_count'] = cp
            e['tp_count'] = tp
        cache.set(key, entries, CACHE_TTL)

    return render(request, 'map_detail.html', {
        'entries': entries,
        'map_name': map_name,
        'is_kz': map_name.startswith('kz_'),
    })


def records(request):
    rows = cache.get('recent_records')
    if rows is None:
        recs = SharpTimerStatsService().get_recent_records(limit=50)
        rows = [
            {'name': r.PlayerName, 'map': r.MapName, 'time': r.FormattedTime,
             'times_finished': r.TimesFinished}
            for r in recs
        ]
        cache.set('recent_records', rows, CACHE_TTL)
    return render(request, 'records.html', {'records': rows})


def _profile_context(steam_id, account=None, is_own=False):
    """Istalgan steam_id uchun profil konteksti (o'zi yoki boshqa o'yinchi).
    account = shu steam_id ga tegishli sayt useri (bo'lsa) — VIP/nom/avatar uchun."""
    is_vip = bool(account and (account.is_staff or account.is_premium()))
    display_name = account.steam_display_name if account else ''
    avatar = account.steam_avatar if account else ''
    faceit_level = getattr(getattr(account, 'steam_profile', None), 'faceit_level', None)

    knife_cur = gloves_cur = None
    if steam_id:
        try:
            selected = skins_service.get_player_skins(steam_id)
            kname = skins_service.get_player_knife(steam_id)
            if kname:
                kdef = next((k['defindex'] for k in skins_service.load_knives()
                             if k['weapon_name'] == kname), None)
                if kdef:
                    info = skins_service.skin_info(kdef, selected.get(kdef)) if selected.get(kdef) else None
                    knife_cur = {'name': info['name'] if info else '',
                                 'image': info['image'] if info else ''}
            gdef = skins_service.get_player_gloves(steam_id)
            if gdef:
                info = skins_service.skin_info(gdef, selected.get(gdef)) if selected.get(gdef) else None
                gloves_cur = {'name': info['name'] if info else '',
                              'image': info['image'] if info else ''}
        except Exception:
            pass

    stats = None
    if steam_id:
        result = SharpTimerStatsService().get_player_stats(steam_id)
        if result:
            stats = {
                'name': result.steam_name,
                'points': result.global_points,
                'rank': result.rank,
                'total_players': result.total_players,
                'maps_completed': result.total_maps_completed,
                'total_runs': result.total_runs,
                'top_records': [
                    {'map': r.MapName, 'time': r.FormattedTime, 'finished': r.TimesFinished}
                    for r in result.top_records
                ],
            }
            if not display_name:
                display_name = result.steam_name
    if not display_name:
        display_name = steam_id or 'Player'

    return {
        'stats': stats, 'steam_id': steam_id, 'is_vip': is_vip,
        'knife_cur': knife_cur, 'gloves_cur': gloves_cur,
        'display_name': display_name, 'avatar': avatar, 'is_own': is_own,
        'faceit_level': faceit_level,
    }


def profile(request):
    if not request.user.is_authenticated:
        return redirect('/auth/login/steam/')
    steam_id = request.user.get_steam_id()
    return render(request, 'profile.html', _profile_context(steam_id, account=request.user, is_own=True))


def public_profile(request, steam_id):
    """Boshqa o'yinchining profili — har qanday kirgan foydalanuvchi ko'ra oladi."""
    if not request.user.is_authenticated:
        return redirect('/auth/login/steam/')
    account = _find_user(steam_id)
    is_own = (steam_id == request.user.get_steam_id())
    return render(request, 'profile.html', _profile_context(steam_id, account=account, is_own=is_own))


def panel(request):
    """Admin boshqaruv paneli — server start/stop, map, kick/ban, RCON, VIP."""
    if not request.user.is_authenticated:
        return redirect('/auth/login/steam/')
    if not request.user.is_staff:
        return render(request, 'panel.html', {'denied': True, 'servers': []})

    servers = [
        {'id': s.id, 'name': s.name, 'port': s.port, 'connect': f"{s.ip}:{s.port}",
         'current_map': s.current_map, 'server_type': s.server_type}
        for s in GameServer.objects.all().order_by('port')
    ]
    return render(request, 'panel.html', {
        'servers': servers,
        'denied': False,
        'vips': _vip_list(),
    })


def _find_user(ident):
    """steamid64, username yoki display_name bo'yicha userni topadi."""
    from django.contrib.auth import get_user_model
    from django.db.models import Q
    User = get_user_model()
    ident = (ident or '').strip()
    if not ident:
        return None
    return (
        User.objects.filter(
            Q(steam_profile__steam_id64=ident) |
            Q(username=ident) |
            Q(steam_profile__display_name=ident)
        ).select_related('steam_profile').first()
    )


def _vip_list(limit=30):
    """Eng yangi obunachilar (default 30 ta), yangi qo'shilgani birinchi."""
    from users.models import Subscription
    out = []
    qs = Subscription.objects.select_related('user', 'user__steam_profile').order_by('-started_at')
    if limit:
        qs = qs[:limit]
    for sub in qs:
        sp = getattr(sub.user, 'steam_profile', None)
        out.append({
            'username': sub.user.username,
            'name': sp.display_name if sp else sub.user.username,
            'steam_id': sp.steam_id64 if sp else '',
            'plan': sub.plan,
            'expires_at': sub.expires_at,
            'active': sub.is_active(),
        })
    return out


def panel_user_search(request):
    """Admin: o'yinchilarni nom/steamid bo'yicha qidirish (VIP berish/profil uchun)."""
    if not request.user.is_authenticated or not request.user.is_staff:
        return JsonResponse({'error': 'forbidden'}, status=403)
    q = (request.GET.get('q') or '').strip()
    if len(q) < 2:
        return JsonResponse({'results': []})
    players = SharpTimerStatsService().search_players(q, limit=20)
    results = [{'name': p.PlayerName, 'steam_id': p.SteamID, 'points': p.GlobalPoints}
               for p in players]
    return JsonResponse({'results': results})


@require_POST
def vip_grant(request):
    """O'yinchiga VIP beradi (admin)."""
    if not request.user.is_staff:
        return JsonResponse({'error': 'forbidden'}, status=403)
    from users.models import Subscription
    from django.utils import timezone
    from datetime import timedelta

    target = _find_user(request.POST.get('ident'))
    if not target:
        return JsonResponse({'error': "O'yinchi topilmadi (steamid/username)"}, status=404)
    try:
        days = int(request.POST.get('days', 30))
    except (TypeError, ValueError):
        return JsonResponse({'error': "kun noto'g'ri"}, status=400)
    plan = request.POST.get('plan', 'vip')
    if plan not in dict(Subscription.PLAN_CHOICES):
        plan = 'vip'

    Subscription.objects.update_or_create(
        user=target,
        defaults={'plan': plan, 'expires_at': timezone.now() + timedelta(days=days),
                  'skins_archived': False},
    )
    # VIP qayta olinса — arxivlangan skinlarni tiklash
    from users.vip_skins import restore_loadout
    restore_loadout(target)
    # Reserved slot: admins.json ni yangilab serverlarga reload
    from .admin_sync import sync_admins
    sync_admins()
    return JsonResponse({'ok': True, 'user': target.username, 'plan': plan, 'days': days})


@require_POST
def vip_revoke(request):
    """VIP ni bekor qiladi (admin)."""
    if not request.user.is_staff:
        return JsonResponse({'error': 'forbidden'}, status=403)
    from users.models import Subscription
    target = _find_user(request.POST.get('ident'))
    if not target:
        return JsonResponse({'error': "O'yinchi topilmadi"}, status=404)
    Subscription.objects.filter(user=target).delete()
    from .admin_sync import sync_admins
    sync_admins()
    return JsonResponse({'ok': True, 'user': target.username})


def _can_paint_skins(user):
    """Bo'yalgan (skinli) variantlar — faqat Pro/VIP (yoki admin).
    Bepul o'yinchilar faqat default pichoq tanlay oladi."""
    if not user.is_authenticated:
        return False
    if user.is_staff:
        return True
    sub = getattr(user, 'subscription', None)
    return bool(sub and sub.is_active() and sub.plan in ('pro', 'vip'))


def skins(request):
    """Skin tanlagich. Har bir o'yinchi DEFAULT pichoq tanlay oladi;
    bo'yalgan (skinli) variantlar faqat Pro/VIP uchun (backendda tekshiriladi)."""
    if not request.user.is_authenticated:
        return redirect('/auth/login/steam/')

    can_paint = _can_paint_skins(request.user)
    steam_id = request.user.get_steam_id()

    weapons, knives, gloves = [], [], []
    knife_cur, gloves_cur = None, None
    agents_t, agents_ct, agent_t_cur, agent_ct_cur = [], [], None, None

    if steam_id:
        # Pichoq modellari — BARCHA o'yinchilar uchun (default tanlash)
        knives = skins_service.load_knives()
        try:
            selected = skins_service.get_player_skins(steam_id)
        except Exception:
            selected = {}
        try:
            seeds = skins_service.get_player_seeds(steam_id)
        except Exception:
            seeds = {}

        # Joriy pichoq (hammaga ko'rsatiladi)
        kname = skins_service.get_player_knife(steam_id)
        if kname:
            kdef = next((k['defindex'] for k in knives if k['weapon_name'] == kname), None)
            if kdef:
                cur = selected.get(kdef)
                info = skins_service.skin_info(kdef, cur) if cur else None
                knife_cur = {'weapon_name': kname, 'defindex': kdef, 'paint': cur,
                             'seed': seeds.get(kdef, 0),
                             'name': info['name'] if info else '', 'image': info['image'] if info else ''}

        # Bo'yalgan variantlar (qurol/qo'lqop/agent) — faqat Pro/VIP
        if can_paint:
            weapons = skins_service.load_weapons()
            gloves = skins_service.load_gloves()
            for w in weapons:
                cur = selected.get(w['defindex'])
                info = skins_service.skin_info(w['defindex'], cur) if cur else None
                w['cur_paint'] = cur
                w['cur_name'] = info['name'] if info else ''
                w['cur_image'] = info['image'] if info else ''

            gdef = skins_service.get_player_gloves(steam_id)
            if gdef:
                cur = selected.get(gdef)
                info = skins_service.skin_info(gdef, cur) if cur else None
                gloves_cur = {'defindex': gdef, 'paint': cur, 'seed': seeds.get(gdef, 0),
                              'name': info['name'] if info else '', 'image': info['image'] if info else ''}

            agents_t = skins_service.load_agents(2)
            agents_ct = skins_service.load_agents(3)
            pa = skins_service.get_player_agents(steam_id)
            agent_t_cur = skins_service.agent_info(pa.get('agent_t'))
            agent_ct_cur = skins_service.agent_info(pa.get('agent_ct'))

    return render(request, 'skins.html', {
        'can_paint': can_paint,
        'steam_id': steam_id,
        'weapons': weapons,
        'knives': knives,
        'gloves': gloves,
        'knife_cur': knife_cur,
        'gloves_cur': gloves_cur,
        'knife_default': skins_service.default_knife_image() if steam_id else '',
        'agents_t': agents_t,
        'agents_ct': agents_ct,
        'agent_t_cur': agent_t_cur,
        'agent_ct_cur': agent_ct_cur,
    })


@require_POST
def skins_save_basic(request):
    """BEPUL: istalgan pichoqning DEFAULT (skinsiz) variantini saqlaydi.
    Har bir kirgan o'yinchi uchun. Xavfsizlik: paint majburan 0, defindex
    server tomonida pichoq nomidan olinadi (foydalanuvchi son/skin yubora olmaydi)."""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Kirish kerak'}, status=403)
    steam_id = request.user.get_steam_id()
    if not steam_id:
        return JsonResponse({'error': "Steam profil ulanmagan"}, status=400)

    # weapon_name ni HAQIQIY pichoqlar ro'yxatiga solishtirib tekshiramiz.
    k = skins_service.knife_model(request.POST.get('weapon_name'))
    if not k:
        return JsonResponse({'error': "noto'g'ri pichoq"}, status=400)

    # paint=0 (default), seed=0 — server majburlaydi, request'dan OLINMAYDI.
    try:
        skins_service.set_knife(steam_id, k['weapon_name'], k['defindex'], 0, 0)
    except Exception as e:
        return JsonResponse({'error': f'DB xatosi: {e}'}, status=500)
    return JsonResponse({'ok': True})


def skins_api_weapon(request, defindex):
    """Bitta qurol/pichoq uchun skinlar (JSON)."""
    if not _can_paint_skins(request.user):
        return JsonResponse({'error': 'forbidden'}, status=403)
    return JsonResponse({'skins': skins_service.skins_for_weapon(int(defindex))})


def skins_api_gloves(request, defindex):
    """Bitta qo'lqop modeli uchun paintlar (JSON)."""
    if not _can_paint_skins(request.user):
        return JsonResponse({'error': 'forbidden'}, status=403)
    return JsonResponse({'skins': skins_service.gloves_skins(int(defindex))})


@require_POST
def skins_save(request):
    """Qurol skinini saqlaydi."""
    if not _can_paint_skins(request.user):
        return JsonResponse({'error': 'Pro yoki VIP kerak'}, status=403)
    steam_id = request.user.get_steam_id()
    if not steam_id:
        return JsonResponse({'error': "Steam profil ulanmagan"}, status=400)
    try:
        defindex = int(request.POST.get('defindex'))
        paint_id = int(request.POST.get('paint_id'))
    except (TypeError, ValueError):
        return JsonResponse({'error': "noto'g'ri parametr"}, status=400)
    try:
        skins_service.set_skin(steam_id, defindex, paint_id)
    except Exception as e:
        return JsonResponse({'error': f'DB xatosi: {e}'}, status=500)
    return JsonResponse({'ok': True})


@require_POST
def skins_save_knife(request):
    """Pichoq modeli + skinini saqlaydi."""
    if not _can_paint_skins(request.user):
        return JsonResponse({'error': 'Pro yoki VIP kerak'}, status=403)
    steam_id = request.user.get_steam_id()
    if not steam_id:
        return JsonResponse({'error': "Steam profil ulanmagan"}, status=400)
    weapon_name = (request.POST.get('weapon_name') or '').strip()
    try:
        defindex = int(request.POST.get('defindex'))
        paint_id = int(request.POST.get('paint_id'))
    except (TypeError, ValueError):
        return JsonResponse({'error': "noto'g'ri parametr"}, status=400)
    if not weapon_name.startswith('weapon_'):
        return JsonResponse({'error': "noto'g'ri pichoq"}, status=400)
    seed = request.POST.get('seed', 0)
    try:
        skins_service.set_knife(steam_id, weapon_name, defindex, paint_id, seed)
    except Exception as e:
        return JsonResponse({'error': f'DB xatosi: {e}'}, status=500)
    return JsonResponse({'ok': True})


@require_POST
def skins_save_all(request):
    """Barcha tanlovlarni (qurol+pichoq+qo'lqop) bir marta saqlaydi (Save tugmasi)."""
    if not _can_paint_skins(request.user):
        return JsonResponse({'error': 'Pro yoki VIP kerak'}, status=403)
    steam_id = request.user.get_steam_id()
    if not steam_id:
        return JsonResponse({'error': "Steam profil ulanmagan"}, status=400)

    import json as _json
    try:
        data = _json.loads(request.body or '{}')
    except ValueError:
        return JsonResponse({'error': "noto'g'ri ma'lumot"}, status=400)

    saved, skipped = 0, 0
    try:
        for defindex, paint in (data.get('weapons') or {}).items():
            try:
                skins_service.set_skin(steam_id, int(defindex), int(paint))
                saved += 1
            except (TypeError, ValueError):
                skipped += 1
        k = data.get('knife')
        if k and str(k.get('weapon_name', '')).startswith('weapon_'):
            try:
                skins_service.set_knife(steam_id, k['weapon_name'], int(k['defindex']),
                                        int(k['paint']), k.get('seed', 0))
                saved += 1
            except (TypeError, ValueError):
                skipped += 1
        g = data.get('gloves')
        if g:
            try:
                skins_service.set_gloves(steam_id, int(g['defindex']), int(g['paint']),
                                         g.get('seed', 0))
                saved += 1
            except (TypeError, ValueError):
                skipped += 1
        if data.get('agent_t'):
            skins_service.set_agent(steam_id, 2, str(data['agent_t']))
            saved += 1
        if data.get('agent_ct'):
            skins_service.set_agent(steam_id, 3, str(data['agent_ct']))
            saved += 1
    except Exception as e:
        return JsonResponse({'error': f'DB xatosi: {e}'}, status=500)

    return JsonResponse({'ok': True, 'saved': saved, 'skipped': skipped})


@require_POST
def skins_save_gloves(request):
    """Qo'lqop modeli + skinini saqlaydi."""
    if not _can_paint_skins(request.user):
        return JsonResponse({'error': 'Pro yoki VIP kerak'}, status=403)
    steam_id = request.user.get_steam_id()
    if not steam_id:
        return JsonResponse({'error': "Steam profil ulanmagan"}, status=400)
    try:
        defindex = int(request.POST.get('defindex'))
        paint_id = int(request.POST.get('paint_id'))
    except (TypeError, ValueError):
        return JsonResponse({'error': "noto'g'ri parametr"}, status=400)
    seed = request.POST.get('seed', 0)
    try:
        skins_service.set_gloves(steam_id, defindex, paint_id, seed)
    except Exception as e:
        return JsonResponse({'error': f'DB xatosi: {e}'}, status=500)
    return JsonResponse({'ok': True})


def logout_view(request):
    auth_logout(request)
    return redirect('/')


def auth_error(request):
    """Steam/social-auth xatosi (masalan 503) bo'lganda do'stona sahifa."""
    return render(request, 'error.html', {
        'title': 'Kirishda xatolik',
        'message': "Steam orqali kirish hozir ishlamayapti (Steam serveri vaqtincha javob bermayapti). "
                   "Iltimos, birozdan so'ng qayta urinib ko'ring.",
        'show_retry_login': True,
    }, status=503)


def error_500(request):
    return render(request, 'error.html', {
        'title': 'Xatolik yuz berdi',
        'message': "Kutilmagan xatolik yuz berdi. Iltimos, birozdan so'ng qayta urinib ko'ring.",
    }, status=500)


def error_404(request, exception):
    return render(request, 'error.html', {
        'title': 'Sahifa topilmadi',
        'message': "Bunday sahifa mavjud emas.",
    }, status=404)
