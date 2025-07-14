# apps/doctores/models.py

from django.db import models
from apps.ubicaciones.models import Distrito

class Doctor(models.Model):
    cmp = models.CharField(max_length=20, unique=True)
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    especialidad = models.CharField(max_length=100)
    direccion = models.TextField()
    fecha_nacimiento = models.DateField(null=True, blank=True)  
    categoria = models.IntegerField(null=True, blank=True)
    ubigeo = models.ForeignKey(Distrito, on_delete=models.SET_NULL, null=True, related_name='doctores')

    def __str__(self):
        return f"{self.nombre} {self.apellido} ({self.cmp})"