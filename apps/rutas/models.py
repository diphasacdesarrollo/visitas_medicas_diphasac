#apps/rutas/models.py
from django.db import models
from apps.doctores.models import Doctor
from apps.usuarios.models import Usuario

class Ruta(models.Model):
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE)
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE)
    fecha_visita = models.DateField()
    estatus = models.CharField(max_length=50)

    def __str__(self):
        return f"{self.usuario.username} → {self.doctor.nombre} ({self.fecha_visita})"
