# apps/asistencia/views.py
from django.shortcuts import render, redirect
from django.utils import timezone
from .models import Asistencia
from django.contrib.auth.decorators import login_required
from django.contrib import messages

@login_required
def registrar_asistencia(request):
    usuario = request.user

    asistencia_incompleta = Asistencia.objects.filter(
        usuario=usuario, fecha_salida__isnull=True
    ).order_by('-id').first()

    ya_ingreso = asistencia_incompleta is not None
    ya_salida = False  # no es necesario revisar porque filtramos por fecha_salida null

    if request.method == 'POST':
        accion = request.POST.get('accion')
        ubicacion = request.POST.get('ubicacion')

        if accion == 'ingreso' and not ya_ingreso:
            Asistencia.objects.create(
                usuario=usuario,
                fecha_ingreso=timezone.now(),
                ubicacion_ingreso=ubicacion
            )
            messages.success(request, "Ingreso registrado correctamente.")
            return redirect('inicio')  # 🔁 ahora también redirige al inicio

        elif accion == 'salida' and ya_ingreso:
            asistencia_incompleta.fecha_salida = timezone.now()
            asistencia_incompleta.ubicacion_salida = ubicacion
            asistencia_incompleta.save()
            messages.success(request, "Salida registrada correctamente.")
            return redirect('inicio')

    context = {
        'ya_ingreso': ya_ingreso,
        'ya_salida': ya_salida,
    }
    return render(request, 'asistencia/registrar.html', context)