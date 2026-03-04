from django.urls import path
from . import views

urlpatterns = [
    path('stats/',        views.stats,        name='api-stats'),
    path('servers/',      views.servers,      name='api-servers'),
    path('achievements/', views.achievements, name='api-achievements'),
    path('videos/',       views.videos,       name='api-videos'),
    path('apply/',        views.apply,        name='api-apply'),
    path('auth/register/', views.register,    name='api-register'),
    path('auth/login/',    views.login_view,  name='api-login'),
]
