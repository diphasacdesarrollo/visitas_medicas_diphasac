# apps/doctores/views.py

from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import Doctor
from apps.ubicaciones.models import Departamento, Provincia, Distrito

@login_required
def crear_doctor(request):
    departamento_id = request.GET.get('departamento')
    provincia_id = request.GET.get('provincia')
    distrito_id = request.GET.get('distrito')

    if request.method == 'POST':
        cmp = request.POST.get('cmp', '').strip()
        nombre = request.POST.get('nombre', '').strip()
        apellido = request.POST.get('apellido', '').strip()
        especialidad = request.POST.get('especialidad', '').strip()
        direccion = request.POST.get('direccion', '').strip()
        categoria = request.POST.get('categoria', '').strip()
        fecha_nacimiento = request.POST.get('fecha_nacimiento') or None
        distrito_final_id = request.POST.get('distrito')

        if not (cmp and nombre and apellido and especialidad and direccion and categoria and distrito_final_id):
            messages.error(request, 'Todos los campos excepto fecha de nacimiento son obligatorios.')
            return redirect('crear_doctor')

        Doctor.objects.create(
            cmp=cmp,
            nombre=nombre.upper(),
            apellido=apellido.upper(),
            especialidad=especialidad.upper(),
            direccion=direccion,
            categoria=categoria,
            fecha_nacimiento=fecha_nacimiento,
            ubigeo_id=distrito_final_id
        )
        messages.success(request, 'Doctor agregado exitosamente.')
        return redirect('crear_ruta')

    departamentos = Departamento.objects.all().order_by('nombre')
    provincias = Provincia.objects.filter(departamento_id=departamento_id) if departamento_id else []
    distritos = Distrito.objects.filter(provincia_id=provincia_id) if provincia_id else []

    return render(request, 'doctores/crear_doctor.html', {
        'departamentos': departamentos,
        'provincias': provincias,
        'distritos': distritos,
        'departamento_actual': int(departamento_id) if departamento_id else None,
        'provincia_actual': int(provincia_id) if provincia_id else None,
        'distrito_actual': int(distrito_id) if distrito_id else None,
    })


def gestionar_medicos(request):
    doctores = Doctor.objects.all()
    return render(request, 'doctores/gestionar_medicos.html', {'doctores': doctores})