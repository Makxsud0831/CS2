from django.conf import settings
from django.contrib import admin
from django.urls import path, include

from .views import (
    home, leaderboard, records, profile, public_profile, logout_view, panel,
    map_leaderboards, map_leaderboard_detail, auth_error,
    skins, skins_api_weapon, skins_save, skins_save_basic,
    skins_api_gloves, skins_save_knife, skins_save_gloves, skins_save_all,
    vip_grant, vip_revoke, panel_user_search, RateLimitedObtainAuthToken,
)

# Do'stona xato sahifalari (DEBUG=False bo'lganda ishlaydi)
handler404 = 'cs2panel.views.error_404'
handler500 = 'cs2panel.views.error_500'

urlpatterns = [
    path('', home, name='home'),
    path('auth-error/', auth_error, name='auth-error'),
    path('leaderboard/', leaderboard, name='leaderboard'),
    path('leaderboard/maps/', map_leaderboards, name='map-leaderboards'),
    path('leaderboard/maps/<str:map_name>/', map_leaderboard_detail, name='map-leaderboard-detail'),
    path('records/', records, name='records'),
    path('profile/', profile, name='profile'),
    path('u/<str:steam_id>/', public_profile, name='public-profile'),
    path('panel/', panel, name='panel'),
    path('panel/vip/grant/', vip_grant, name='vip-grant'),
    path('panel/vip/revoke/', vip_revoke, name='vip-revoke'),
    path('panel/users/search/', panel_user_search, name='panel-user-search'),
    path('skins/', skins, name='skins'),
    path('skins/api/weapon/<int:defindex>/', skins_api_weapon, name='skins-api-weapon'),
    path('skins/api/gloves/<int:defindex>/', skins_api_gloves, name='skins-api-gloves'),
    path('skins/save/', skins_save, name='skins-save'),
    path('skins/save-basic/', skins_save_basic, name='skins-save-basic'),
    path('skins/save-knife/', skins_save_knife, name='skins-save-knife'),
    path('skins/save-gloves/', skins_save_gloves, name='skins-save-gloves'),
    path('skins/save-all/', skins_save_all, name='skins-save-all'),
    path('logout/', logout_view, name='logout'),
    path(settings.ADMIN_URL, admin.site.urls),
    path('auth/', include('social_django.urls', namespace='social')),
    path('api/auth/token/', RateLimitedObtainAuthToken.as_view(), name='api-token'),
    path('api/servers/', include('servers.urls')),
    path('api/users/', include('users.urls')),
    path('api/records/', include('records.urls')),
]
