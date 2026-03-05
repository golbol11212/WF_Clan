from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('clan.urls')),
    path('hub/',    TemplateView.as_view(template_name='wf-hub.html')),
    path('auth/',   TemplateView.as_view(template_name='wf-auth.html')),
    path('roster/', TemplateView.as_view(template_name='wf-roster.html')),
    path('wipe/',   TemplateView.as_view(template_name='wf-wipe.html')),
    path('',        TemplateView.as_view(template_name='wf-clan.html')),
]
