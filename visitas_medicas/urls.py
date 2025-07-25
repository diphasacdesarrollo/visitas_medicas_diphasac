#visitas_medicas/urls.py
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from apps.usuarios.views import cambiar_password, inicio

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/login/', auth_views.LoginView.as_view(), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('cambiar-password/', cambiar_password, name='cambiar_password'),
    path('', inicio, name='inicio'),
    path('visitas/', include('apps.visitas.urls', namespace='visitas')),
    path('asistencia/', include('apps.asistencia.urls')),
    path('doctores/', include(('apps.doctores.urls', 'doctores'), namespace='doctores')),
    path('rutas/', include('apps.rutas.urls')),
    path('api/', include('apps.ubicaciones.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])