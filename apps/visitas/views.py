# apps/visitas/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from apps.visitas.models import Visita, DetalleVisita, ProductoPresentado
from apps.productos.models import Producto
from apps.rutas.models import Ruta
from apps.doctores.models import Doctor
from django.utils.timezone import now
from apps.rutas.utils import actualizar_estados_de_rutas
from django.db.models import Count, Avg, DurationField, ExpressionWrapper, F
from django.core.paginator import Paginator
from django.db.models.functions import ExtractIsoWeekDay, TruncWeek, Coalesce
from django.db.models import Exists, OuterRef, Value, CharField, Case, When, IntegerField, BooleanField, Subquery, Count
from datetime import date, datetime, timedelta
from django.contrib.auth import get_user_model
import json

@login_required
def iniciar_visita(request, ruta_id=None, doctor_id=None):
    user = request.user
    ubicacion = request.GET.get('ubicacion', '')
    visita_es_emergencia = False
    ruta = None
    doctor = None

    hoy = timezone.now().date()

    if ruta_id:
        # Solo puede abrir rutas propias
        ruta = get_object_or_404(Ruta, id=ruta_id, usuario=user)
        doctor = ruta.doctor
    elif doctor_id:
        doctor = get_object_or_404(Doctor, id=doctor_id)
        # Bloqueo: visitador solo con sus médicos
        if not (user.is_superuser or user.rol == 'supervisor'):
            if doctor.visitador_id != user.id:
                messages.error(request, "No tienes permiso para visitar a este doctor.")
                return redirect('visitas:gestionar_visitas_medicas')
        visita_es_emergencia = True
    else:
        return redirect('visitas:gestionar_visitas_medicas')

    # Buscar si ya existe visita del día (por ruta o por doctor sin ruta)
    filtros = {'usuario': user, 'doctor': doctor, 'fecha_inicio__date': hoy}
    if ruta:
        filtros['ruta'] = ruta
    else:
        filtros['ruta__isnull'] = True

    visita = Visita.objects.filter(**filtros).first()

    if request.method == 'POST':
        if not visita:
            ubicacion = request.POST.get('ubicacion', '')
            visita = Visita.objects.create(
                usuario=user,
                doctor=doctor,
                ruta=ruta,
                fecha_inicio=now(),
                ubicacion_inicio=ubicacion
            )
        request.session['visita_id'] = visita.id
        return redirect('visitas:agregar_productos')

    if visita:
        request.session['visita_id'] = visita.id

    return render(request, 'visitas/iniciar_visita.html', {
        'doctor': doctor,
        'ubicacion': ubicacion,
        'visita_es_emergencia': visita_es_emergencia
    })

@login_required
def gestionar_visitas_medicas(request):
    actualizar_estados_de_rutas()

    user = request.user

    if user.is_superuser or getattr(user, 'rol', None) == 'supervisor':
        rutas = (Ruta.objects
                 .select_related('doctor', 'usuario')
                 .order_by('-fecha_visita'))
        doctores_base = Doctor.objects.all()
    else:
        rutas = (Ruta.objects
                 .filter(usuario=user)
                 .select_related('doctor')
                 .order_by('-fecha_visita'))
        doctores_base = Doctor.objects.filter(visitador_id=user.id)

    # ===== Periodo mensual (MES ACTUAL) =====
    hoy = timezone.localdate()
    month_start = hoy.replace(day=1)
    if month_start.month == 12:
        next_month_start = date(month_start.year + 1, 1, 1)
    else:
        next_month_start = date(month_start.year, month_start.month + 1, 1)

    # ¿Visitado al menos una vez este mes por este usuario?
    visitado_mes_qs = Visita.objects.filter(
        usuario=user,
        doctor_id=OuterRef('pk'),
        fecha_inicio__date__gte=month_start,
        fecha_inicio__date__lt=next_month_start,
    )

    # Visitas del mes (contador)
    visitas_count_sq = (
        Visita.objects
        .filter(
            usuario=user,
            doctor_id=OuterRef('pk'),
            fecha_inicio__date__gte=month_start,
            fecha_inicio__date__lt=next_month_start,
        )
        .values('doctor_id')
        .annotate(c=Count('id'))
        .values('c')[:1]
    )

    # 🔹 NUEVO: última visita (para el usuario actual), toma la fecha más reciente
    ultima_visita_sq = (
        Visita.objects
        .filter(
            usuario=user,                # última visita realizada por este usuario
            doctor_id=OuterRef('pk'),
        )
        .order_by('-fecha_inicio')
        .values('fecha_inicio')[:1]
    )

    # (Opcional) planificado en rutas futuras de este mes → amarillo
    planificado_qs = Ruta.objects.filter(
        usuario_id=user.id,
        doctor_id=OuterRef('pk'),
        fecha_visita__gte=hoy,
        fecha_visita__lt=next_month_start,
    )

    doctores = (
        doctores_base
        .annotate(
            visitas_mes=Coalesce(Subquery(visitas_count_sq, output_field=IntegerField()), Value(0)),
            visitado_mes=Exists(visitado_mes_qs),
            planificado=Exists(planificado_qs),

            # 🔹 NUEVO: campo que usas en el template
            ultima_visita=Subquery(ultima_visita_sq),

            semaforo=Case(
                When(visitado_mes=True, then=Value('verde')),
                When(visitado_mes=False, planificado=True, then=Value('amarillo')),
                default=Value('rojo'),
                output_field=CharField(),
            ),
            estado_label=Case(
                When(visitado_mes=True, then=Value('Cubierto')),
                When(planificado=True, then=Value('Planificado')),
                default=Value('Pendiente'),
                output_field=CharField(),
            ),
            visitado_bool=Case(
                When(visitas_mes__gt=0, then=Value(True)),
                default=Value(False),
                output_field=BooleanField(),
            ),
        )
        .only('id', 'cmp', 'apellido', 'nombre', 'especialidad')
    )

    return render(request, 'visitas/gestionar_visitas_medicas.html', {
        'rutas': rutas,
        'doctores': doctores,
    })

@login_required
def agregar_productos(request):
    # 1) Recuperar la visita desde sesión (o corta con fallback SEGURO)
    visita_id = request.session.get('visita_id')
    if not visita_id:
        messages.error(request, "No se ha iniciado una visita.")
        # ⚠️ No podemos volver a 'iniciar_visita' sin parámetros -> ir a la pantalla padre
        return redirect('visitas:gestionar_visitas_medicas')

    # 2) Garantizar que la visita pertenece al usuario logueado
    visita = get_object_or_404(Visita, id=visita_id, usuario=request.user)

    if request.method == 'POST':
        accion = request.POST.get('accion')

        # ✅ Guardar productos presentados (checkboxes)
        productos_presentados_ids = request.POST.getlist('productos_presentados')
        (ProductoPresentado.objects
            .filter(visita=visita)
            .exclude(producto_id__in=productos_presentados_ids)
            .delete())
        for prod_id in productos_presentados_ids:
            ProductoPresentado.objects.get_or_create(visita=visita, producto_id=prod_id)

        if accion == 'agregar_entrega':
            producto_id = request.POST.get('producto')
            cantidad = request.POST.get('cantidad')
            tipo_entrega = request.POST.get('tipo_entrega')

            if producto_id and cantidad and tipo_entrega:
                DetalleVisita.objects.create(
                    visita=visita,
                    producto_id=producto_id,
                    cantidad=cantidad,
                    tipo_entrega=tipo_entrega
                )
                messages.success(request, "Entrega registrada correctamente.")
            else:
                messages.warning(request, "Complete todos los campos de entrega.")

        elif accion == 'finalizar':
            visita.comentarios = request.POST.get('comentarios', '')
            visita.fecha_final = timezone.now()
            visita.duracion = visita.calcular_duracion()
            visita.save()

            # ✅ Intentar actualizar la ruta del día si aplica
            try:
                ruta = Ruta.objects.get(
                    usuario=request.user,
                    doctor=visita.doctor,
                    fecha_visita=visita.fecha_inicio.date()
                )
                ruta.actualizar_estatus()
            except Ruta.DoesNotExist:
                pass

            # Limpia sesión y vuelve al inicio
            request.session.pop('visita_id', None)
            messages.success(request, "Visita finalizada correctamente.")
            return redirect('inicio')

    productos_promocionales = Producto.objects.filter(tipo_producto='promocional')
    productos_muestra = Producto.objects.filter(tipo_producto='muestra')
    productos_merch = Producto.objects.filter(tipo_producto='merch')

    productos_presentados = (ProductoPresentado.objects
                             .filter(visita=visita)
                             .select_related('producto'))
    entregas = (DetalleVisita.objects
                .filter(visita=visita)
                .select_related('producto'))
    productos_presentados_ids = productos_presentados.values_list('producto_id', flat=True)

    imagen_productos = {
        'DUO DAPHA 10': 'test.jpg',
        'DUO DAPHA 5': 'duo-dapha-5.jpg',
        'DAPHA 10': 'dapha-10.jpg',
    }

    return render(request, 'visitas/agregar_productos.html', {
        'visita': visita,
        'productos_promocionales': productos_promocionales,
        'productos_muestra': productos_muestra,
        'productos_merch': productos_merch,
        'productos_presentados': productos_presentados,
        'productos_presentados_ids': productos_presentados_ids,
        'entregas': entregas,
        'imagen_productos': imagen_productos,
    })

def actualizar_estados_de_rutas():
    hoy = timezone.now().date()
    rutas = Ruta.objects.select_related('doctor', 'usuario')

    for ruta in rutas:
        # Si hay una visita asociada a esta ruta (usuario + doctor + fecha), está completada
        existe_visita = Visita.objects.filter(
            doctor=ruta.doctor,
            usuario=ruta.usuario,
            fecha_inicio__date=ruta.fecha_visita
        ).exists()

        if existe_visita:
            ruta.estatus = 'completado'
        elif ruta.fecha_visita < hoy:
            ruta.estatus = 'retraso'
        elif ruta.fecha_visita >= hoy:
            ruta.estatus = 'pendiente'

        ruta.save()

def _aware(dt):
    return dt if timezone.is_aware(dt) else timezone.make_aware(dt)

def _week_bounds(year:int, week:int):
    # Lunes de esa semana ISO y lunes siguiente
    start_d = date.fromisocalendar(year, week, 1)
    end_d   = start_d + timedelta(days=7)
    return (
        _aware(datetime.combine(start_d, datetime.min.time())),
        _aware(datetime.combine(end_d,   datetime.min.time())),
        start_d
    )


@login_required
def ver_historial(request):
    User = get_user_model()
    user = request.user

    # ====== quién es el "dueño" del historial que mostraremos ======
    rep_id = request.GET.get("rep_id")
    is_supervisor = user.is_superuser or getattr(user, "rol", "") == "supervisor"

    usuario_target = user  # por defecto, uno mismo
    visitadores_qs = User.objects.none()

    if is_supervisor:
        # lista de visitadores para el selector
        visitadores_qs = User.objects.filter(rol="visitador").order_by("first_name", "last_name")

        if rep_id:  # si el supervisor eligió a alguien
            usuario_target = get_object_or_404(User, id=rep_id, rol="visitador")

    # =========================
    # 1) HISTORIAL SEMANAL
    # =========================
    hoy = timezone.localdate()
    y, w, _ = hoy.isocalendar()
    semana = int(request.GET.get("semana", w))
    año    = int(request.GET.get("año", y))

    weekpick = request.GET.get("weekpick")
    if weekpick:
        try:
            a, ws = weekpick.split("-W")
            año = int(a); semana = int(ws)
        except Exception:
            pass

    week_start_date = date.fromisocalendar(año, semana, 1)
    week_end_date   = week_start_date + timedelta(days=7)

    visitas_qs = (
        Visita.objects
        .filter(
            usuario=usuario_target,                                 # <<< clave
            fecha_inicio__date__gte=week_start_date,
            fecha_inicio__date__lt=week_end_date,
        )
        .select_related('doctor')
        .order_by('-fecha_inicio')
    )
    detalles_qs = (
        DetalleVisita.objects
        .filter(
            visita__usuario=usuario_target,                         # <<< clave
            visita__fecha_inicio__date__gte=week_start_date,
            visita__fecha_inicio__date__lt=week_end_date,
        )
        .select_related('visita', 'visita__doctor', 'producto')
        .order_by('-visita__fecha_inicio')
    )
    presentados_qs = (
        ProductoPresentado.objects
        .filter(
            visita__usuario=usuario_target,                         # <<< clave
            visita__fecha_inicio__date__gte=week_start_date,
            visita__fecha_inicio__date__lt=week_end_date,
        )
        .select_related('visita', 'visita__doctor', 'producto')
        .order_by('-visita__fecha_inicio')
    )

    total_visitas_semana = visitas_qs.count()
    tiempo_promedio = (
        visitas_qs.exclude(fecha_final=None)
        .annotate(dur_delta=ExpressionWrapper(F('fecha_final') - F('fecha_inicio'), output_field=DurationField()))
        .aggregate(prom=Avg('dur_delta'))['prom'] or timedelta()
    )
    total_productos_presentados = presentados_qs.count()
    total_entregas = detalles_qs.count()

    por_dia = (
        visitas_qs
        .annotate(dow=ExtractIsoWeekDay('fecha_inicio'))
        .values('dow').annotate(total=Count('id')).order_by('dow')
    )
    nombres_dias = ["Lun","Mar","Mié","Jue","Vie","Sáb","Dom"]
    mapa = {d['dow']: d['total'] for d in por_dia}
    visitas_semana_labels = nombres_dias
    visitas_semana_data   = [mapa.get(i, 0) for i in range(1, 8)]

    def _first_token(s: str) -> str:
        s = (s or "").strip()
        return s.split()[0] if s else ""

    top_raw = (
        visitas_qs
        .values('doctor__apellido', 'doctor__nombre')
        .annotate(total=Count('id'))
        .order_by('-total')[:5]
    )
    top_doctores_labels = [
        (f"{_first_token(d['doctor__apellido'])} {_first_token(d['doctor__nombre'])}".strip() or "Sin nombre")
        for d in top_raw
    ]
    top_doctores_data = [d['total'] for d in top_raw]

    prev_monday = week_start_date - timedelta(days=7)
    next_monday = week_start_date + timedelta(days=7)
    prev_year, prev_week, _ = prev_monday.isocalendar()
    next_year, next_week, _ = next_monday.isocalendar()
    weekpick_value = f"{año}-W{semana:02d}"

    # =========================
    # 2) COBERTURA MENSUAL
    # =========================
    month_param = request.GET.get("month")
    if month_param:
        try:
            m_year, m_month = map(int, month_param.split("-"))
            month_start_date = date(m_year, m_month, 1)
        except Exception:
            month_start_date = hoy.replace(day=1)
    else:
        month_start_date = hoy.replace(day=1)

    if month_start_date.month == 12:
        next_month_start = date(month_start_date.year + 1, 1, 1)
    else:
        next_month_start = date(month_start_date.year, month_start_date.month + 1, 1)

    asignados_qs = Doctor.objects.filter(visitador=usuario_target).only('id')  # <<< clave
    asignados_total = asignados_qs.count()

    visitas_mes_qs = (
        Visita.objects
        .filter(
            usuario=usuario_target,                                  # <<< clave
            fecha_inicio__date__gte=month_start_date,
            fecha_inicio__date__lt=next_month_start,
        )
        .values('doctor_id')
        .distinct()
    )
    visitados_count = asignados_qs.filter(id__in=visitas_mes_qs).count()
    pendientes = max(asignados_total - visitados_count, 0)
    cobertura_pct = round(100 * visitados_count / asignados_total) if asignados_total else 0

    cobertura_labels = ["Visitados", "Pendientes"]
    cobertura_data   = [visitados_count, pendientes]
    month_value = f"{month_start_date:%Y-%m}"

    # nombre que muestra el título
    titulo_nombre = usuario_target.get_full_name() or usuario_target.username

    return render(request, 'visitas/historial.html', {
        # datos actuales...
        'total_visitas_semana': total_visitas_semana,
        'total_productos_presentados': total_productos_presentados,
        'total_entregas': total_entregas,
        'tiempo_promedio': round(tiempo_promedio.total_seconds()/60),
        'visitas_semana_labels': json.dumps(visitas_semana_labels),
        'visitas_semana_data': json.dumps(visitas_semana_data),
        'top_doctores_labels': json.dumps(top_doctores_labels),
        'top_doctores_data': json.dumps(top_doctores_data),
        'visitas': visitas_qs,
        'detalles': detalles_qs,
        'presentados': presentados_qs,
        'semana_actual': semana, 'año_actual': año,
        'semana_anterior': prev_week, 'año_anterior': prev_year,
        'semana_siguiente': next_week, 'año_siguiente': next_year,
        'weekpick_value': weekpick_value,
        'cobertura_labels': json.dumps(cobertura_labels),
        'cobertura_data': json.dumps(cobertura_data),
        'cobertura_pct': cobertura_pct,
        'visitados_count': visitados_count,
        'asignados_total': asignados_total,
        'month_value': month_value,
        'pendientes': pendientes,

        # <<< para el selector de supervisor
        'is_supervisor': is_supervisor,
        'visitadores': visitadores_qs,
        'rep_id': str(rep_id or ""),
        'titulo_nombre': titulo_nombre,
    })