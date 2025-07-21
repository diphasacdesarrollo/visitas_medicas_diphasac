from django.db import models
from apps.doctores.models import Doctor
from apps.usuarios.models import Usuario
from django.utils import timezone

class Ruta(models.Model):
    ESTADOS = (
        ('pendiente', 'Pendiente'),
        ('completado', 'Completado'),
        ('retraso', 'Retraso'),
        ('emergencia', 'Emergencia'),
    )

    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE)
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE)
    fecha_visita = models.DateField()
    estatus = models.CharField(max_length=50, choices=ESTADOS, default='pendiente')

    def __str__(self):
        return f"{self.usuario.username} → {self.doctor.nombre} ({self.fecha_visita})"

    def actualizar_estatus(self):
        """
        Cambia automáticamente el estatus según la fecha actual 
        y la existencia de una visita finalizada asociada a esta ruta.
        """
        from apps.visitas.models import Visita

        hoy = timezone.localdate()
        tiene_visita = Visita.objects.filter(ruta=self, fecha_final__isnull=False).exists()

        if tiene_visita:
            self.estatus = 'completado'
        elif self.fecha_visita < hoy:
            self.estatus = 'retraso'
        elif self.estatus != 'emergencia':  # mantener si ya era emergencia
            self.estatus = 'pendiente'

        self.save()