# apps/doctores/models.py
from django.db import models
from apps.productos.models import Producto
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

class Prescripcion(models.Model):
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='prescripciones')
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    rank_tam = models.PositiveIntegerField(verbose_name="Ranking por Tamaño de Mercado")
    ms_tam = models.FloatField(verbose_name="Market Share por Tamaño")
    rank_trim = models.PositiveIntegerField(verbose_name="Ranking Trimestral")
    ms_trim = models.FloatField(verbose_name="Market Share Trimestral")
    
    fecha_registro = models.DateField(auto_now_add=True)

    class Meta:
        verbose_name = "Prescripción"
        verbose_name_plural = "Prescripciones"
        unique_together = ('doctor', 'producto')  # Un producto solo una vez por doctor

    def __str__(self):
        return f"{self.doctor} - {self.producto}"