from django.urls import path
from . import views

urlpatterns = [
    path('stats/',        views.stats,        name='api-stats'),
    path('servers/',      views.servers,      name='api-servers'),
    path('achievements/', views.achievements, name='api-achievements'),
    path('videos/',       views.videos,       name='api-videos'),
    path('roster/',       views.roster,       name='api-roster'),
    path('wipe/current/', views.wipe_current, name='api-wipe-current'),
    path('wipe/archive/', views.wipe_archive, name='api-wipe-archive'),
    path('apply/',        views.apply,        name='api-apply'),
    path('auth/register/',     views.register,     name='api-register'),
    path('auth/login/',        views.login_view,   name='api-login'),
    path('auth/steam-lookup/', views.steam_lookup, name='api-steam-lookup'),
    path('auth/user-info/',    views.user_info,    name='api-user-info'),
]
