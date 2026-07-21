from django.urls import path
from .views import (
    ServerListView,
    ServerStatusView,
    public_server_status,
    RCONCommandView,
    ChangeMapView,
    KickPlayerView,
    BanPlayerView,
    UnbanPlayerView,
    SayView,
    RestartView,
    PlayersWithIDsView,
    ExecCfgView,
    MapPoolView,
    MapDetailView,
    SetCurrentMapView,
    StartServerView,
    StopServerView,
)

urlpatterns = [
    # Serverlar ro'yxati
    path('', ServerListView.as_view(), name='server-list'),

    # Bosh sahifa uchun jonli holat (anonim ham ko'radi)
    path('public-status/', public_server_status, name='public-server-status'),

    # Status va o'yinchilar
    path('<int:server_id>/status/', ServerStatusView.as_view(), name='server-status'),
    path('<int:server_id>/players/', PlayersWithIDsView.as_view(), name='server-players'),

    # Boshqaruv (admin only)
    path('<int:server_id>/rcon/', RCONCommandView.as_view(), name='server-rcon'),
    path('<int:server_id>/map/', ChangeMapView.as_view(), name='server-map'),
    path('<int:server_id>/restart/', RestartView.as_view(), name='server-restart'),
    path('<int:server_id>/exec/', ExecCfgView.as_view(), name='server-exec'),

    path('<int:server_id>/start/', StartServerView.as_view(), name='server-start'),
    path('<int:server_id>/stop/', StopServerView.as_view(), name='server-stop'),

    # O'yinchi boshqaruvi (admin only)
    path('<int:server_id>/kick/', KickPlayerView.as_view(), name='server-kick'),
    path('<int:server_id>/ban/', BanPlayerView.as_view(), name='server-ban'),
    path('<int:server_id>/unban/', UnbanPlayerView.as_view(), name='server-unban'),
    path('<int:server_id>/say/', SayView.as_view(), name='server-say'),

    # Map pool
    path('<int:server_id>/maps/', MapPoolView.as_view(), name='server-maps'),
    path('<int:server_id>/maps/<int:map_id>/', MapDetailView.as_view(), name='server-map-detail'),
    path('<int:server_id>/maps/<int:map_id>/set/', SetCurrentMapView.as_view(), name='server-map-set'),
]