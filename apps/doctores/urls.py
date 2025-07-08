#apps/doctores/urls.py
from django.urls import path
from .views import crear_doctor,gestionar_medicos

urlpatterns = [
    path('nuevo-doctor/', crear_doctor, name='crear_doctor'),
    path('gestionar/', gestionar_medicos, name='gestionar_medicos')

]