from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('servers.urls')),
    path('auth/', include('social_django.urls', namespace='social')),
    path('api/servers/', include('servers.urls')),
    path('api/users/', include('users.urls')),
]
