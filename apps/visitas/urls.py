# apps/visitas/urls.py
from django.urls import path
from . import views

app_name = 'visitas'

urlpatterns = [
    path('iniciar-visita/<int:doctor_id>/', views.iniciar_visita, name='iniciar_visita'),
    path('agregar-productos/', views.agregar_productos, name='agregar_productos'),
    path('gestionar-visitas/', views.gestionar_visitas_medicas, name='gestionar_visitas_medicas'),
]