from django.urls import path
from .views import (
    ServerStatusView,
    RCONCommandView,
    ChangeMapView,
    KickPlayerView,
)

urlpatterns = [
    path('servers/<int:server_id>/status/', ServerStatusView.as_view()),
    path('servers/<int:server_id>/rcon/', RCONCommandView.as_view()),
    path('servers/<int:server_id>/map/', ChangeMapView.as_view()),    # ← bor?
    path('servers/<int:server_id>/kick/', KickPlayerView.as_view()),  # ← bor?
]