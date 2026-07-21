from django.urls import path
from .views import (
    MapLeaderboardView,
    PlayerRecordsView,
    MyRecordsView,
    MyHistoryView,
    MyCompletionsView,
    submit_run,
    player_stats,
    my_stats,
    st_map_leaderboard,
    global_top,
    recent_records,
    search_players,
    submit_checkpoints,
)

urlpatterns = [
    # Django records (submit va o'z rekordalri)
    path('submit/', submit_run, name='record-submit'),
    path('me/', MyRecordsView.as_view(), name='my-records'),
    path('me/history/', MyHistoryView.as_view(), name='my-history'),
    path('me/completions/', MyCompletionsView.as_view(), name='my-completions'),
    path('maps/<int:map_id>/leaderboard/', MapLeaderboardView.as_view(), name='map-leaderboard'),
    path('players/<int:user_id>/', PlayerRecordsView.as_view(), name='player-records'),

    # SharpTimer stats
    path('stats/me/', my_stats, name='my-stats'),
    path('stats/<str:steam_id>/', player_stats, name='player-stats'),
    path('st/maps/<str:map_name>/leaderboard/', st_map_leaderboard, name='st-map-leaderboard'),
    path('st/top/', global_top, name='global-top'),
    path('st/recent/', recent_records, name='recent-records'),

    # Qidiruv
    path('search/', search_players, name='player-search'),

    # CP/TP statistikasi (CS2 server yuboradi)
    path('checkpoints/', submit_checkpoints, name='submit-checkpoints'),
]
