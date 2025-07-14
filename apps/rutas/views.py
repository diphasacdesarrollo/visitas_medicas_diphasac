#apps/rutas/views.py
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from apps.doctores.models import Doctor
from apps.usuarios.models import Usuario
from .models import Ruta  
from datetime import date
from apps.ubicaciones.models import Departamento, Provincia, Distrito

@login_required
def crear_ruta(request):
    departamento_id = request.GET.get('departamento')
    provincia_id = request.GET.get('provincia')
    distrito_id = request.GET.get('distrito')

    doctores_qs = Doctor.objects.all()
    if distrito_id:
        doctores_qs = doctores_qs.filter(ubigeo_id=distrito_id)
    elif provincia_id:
        distritos = Distrito.objects.filter(provincia_id=provincia_id)
        doctores_qs = doctores_qs.filter(ubigeo__in=distritos)
    elif departamento_id:
        provincias = Provincia.objects.filter(departamento_id=departamento_id)
        distritos = Distrito.objects.filter(provincia__in=provincias)
        doctores_qs = doctores_qs.filter(ubigeo__in=distritos)

    departamentos = Departamento.objects.all().order_by('nombre')
    provincias = Provincia.objects.filter(departamento_id=departamento_id).order_by('nombre') if departamento_id else []
    distritos = Distrito.objects.filter(provincia_id=provincia_id).order_by('nombre') if provincia_id else []

    visitadores = Usuario.objects.filter(rol='visitador') if request.user.is_superuser or request.user.rol == 'supervisor' else []

    if request.method == 'POST':
        doctor_id = request.POST.get('doctor_id')
        fecha_visita = request.POST.get('fecha_visita')

        if request.user.is_superuser or request.user.rol == 'supervisor':
            usuario_id = request.POST.get('visitador_id')
            if not usuario_id:
                messages.error(request, "Debes seleccionar un visitador.")
                return redirect('crear_ruta')
        else:
            usuario_id = request.user.id

        if not doctor_id or not fecha_visita:
            messages.error(request, "Todos los campos son obligatorios.")
            return redirect('crear_ruta')

        fecha_seleccionada = date.fromisoformat(fecha_visita)
        hoy = date.today()
        if fecha_seleccionada > hoy:
            estado = 'pendiente'
        elif fecha_seleccionada == hoy:
            estado = 'completado'
        else:
            estado = 'atrasado'

        Ruta.objects.create(
            doctor_id=doctor_id,
            usuario_id=usuario_id,
            fecha_visita=fecha_visita,
            estatus=estado
        )
        messages.success(request, "Ruta registrada exitosamente.")
        return redirect('crear_ruta')

    return render(request, 'rutas/crear_ruta.html', {
        'doctores': doctores_qs,
        'departamentos': departamentos,
        'provincias': provincias,
        'distritos': distritos,
        'visitadores': visitadores,
        'departamento_actual': int(departamento_id) if departamento_id else None,
        'provincia_actual': int(provincia_id) if provincia_id else None,
        'distrito_actual': int(distrito_id) if distrito_id else None,
    })