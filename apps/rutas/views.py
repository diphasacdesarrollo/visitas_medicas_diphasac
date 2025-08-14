# apps/rutas/views.py
from datetime import date

from django.template.loader import render_to_string
from django.http import JsonResponse

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q              # 👈  IMPORTANTE
from django.shortcuts import redirect, render
from django.utils.timezone import localdate

from apps.doctores.models import Doctor
from apps.ubicaciones.models import Departamento, Distrito, Provincia
from apps.usuarios.models import Usuario
from .models import Ruta


@login_required
def crear_ruta(request):
    from datetime import date
    from django.db.models import Q
    from django.utils.timezone import localdate

    # ---------------------- parámetros GET ----------------------
    departamento_id = request.GET.get("departamento")
    provincia_id    = request.GET.get("provincia")
    distrito_id     = request.GET.get("distrito")
    busqueda        = (request.GET.get("busqueda") or "").strip()
    # opcional: para que admin/supervisor filtren doctores por visitador
    visitador_filtro_id = request.GET.get("visitador_id")

    # ---------------------- queryset base -----------------------
    doctores_qs = Doctor.objects.all()

    # --- filtro por rol del usuario
    if request.user.is_superuser or getattr(request.user, "rol", "") == "supervisor":
        # si viene un filtro explícito de visitador, se aplica
        if visitador_filtro_id:
            doctores_qs = doctores_qs.filter(visitador_id=visitador_filtro_id)
    else:
        # visitador normal: solo sus doctores
        doctores_qs = doctores_qs.filter(visitador_id=request.user.id)

    # --- filtro geográfico
    if distrito_id:
        doctores_qs = doctores_qs.filter(ubigeo_id=distrito_id)

    elif provincia_id:
        distritos    = Distrito.objects.filter(provincia_id=provincia_id)
        doctores_qs  = doctores_qs.filter(ubigeo__in=distritos)

    elif departamento_id:
        provincias   = Provincia.objects.filter(departamento_id=departamento_id)
        distritos    = Distrito.objects.filter(provincia__in=provincias)
        doctores_qs  = doctores_qs.filter(ubigeo__in=distritos)

    # --- filtro por nombre / apellido / CMP
    if busqueda:
        doctores_qs = doctores_qs.filter(
            Q(nombre__icontains=busqueda) |
            Q(apellido__icontains=busqueda) |
            Q(cmp__icontains=busqueda)
        )

    # ---------------------- catálogos ---------------------------
    departamentos = Departamento.objects.order_by("nombre")
    provincias    = Provincia.objects.filter(departamento_id=departamento_id).order_by("nombre") if departamento_id else []
    distritos     = Distrito.objects.filter(provincia_id=provincia_id).order_by("nombre")        if provincia_id    else []

    visitadores   = (
        Usuario.objects.filter(rol="visitador")
        if (request.user.is_superuser or getattr(request.user, "rol", "") == "supervisor")
        else []
    )

    # ---------------------- POST: crear ruta --------------------
    if request.method == "POST":
        doctor_id    = request.POST.get("doctor_id")
        fecha_visita = request.POST.get("fecha_visita")

        if request.user.is_superuser or getattr(request.user, "rol", "") == "supervisor":
            usuario_id = request.POST.get("visitador_id")
            if not usuario_id:
                messages.error(request, "Debes seleccionar un visitador.")
                return redirect("crear_ruta")

            # validar que el doctor pertenece al visitador elegido
            if not Doctor.objects.filter(id=doctor_id, visitador_id=usuario_id).exists():
                messages.error(request, "El doctor seleccionado no pertenece al visitador elegido.")
                return redirect("crear_ruta")
        else:
            usuario_id = request.user.id
            # validar que el doctor pertenece al visitador logueado
            if not Doctor.objects.filter(id=doctor_id, visitador_id=usuario_id).exists():
                messages.error(request, "No tienes permiso para programar rutas con este doctor.")
                return redirect("crear_ruta")

        if not doctor_id or not fecha_visita:
            messages.error(request, "Todos los campos son obligatorios.")
            return redirect("crear_ruta")

        fecha_seleccionada = date.fromisoformat(fecha_visita)
        hoy                = localdate()
        if   fecha_seleccionada > hoy: estado = "pendiente"
        elif fecha_seleccionada == hoy: estado = "completado"
        else:                           estado = "atrasado"

        Ruta.objects.create(
            doctor_id    = doctor_id,
            usuario_id   = usuario_id,
            fecha_visita = fecha_visita,
            estatus      = estado,
        )
        messages.success(request, "Ruta registrada exitosamente.")
        return redirect("crear_ruta")

    # ---------------------- render ------------------------------
    context = {
        "doctores": doctores_qs,
        "departamentos": departamentos,
        "provincias": provincias,
        "distritos": distritos,
        "visitadores": visitadores,
        "departamento_actual": int(departamento_id) if departamento_id else None,
        "provincia_actual": int(provincia_id) if provincia_id else None,
        "distrito_actual": int(distrito_id) if distrito_id else None,
        "busqueda": busqueda,
        "visitador_actual": int(visitador_filtro_id) if visitador_filtro_id else None,  # opcional
    }

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        html = render_to_string("rutas/tabla_doctores.html", context, request=request)
        return JsonResponse({"html": html})

    return render(request, "rutas/crear_ruta.html", context)