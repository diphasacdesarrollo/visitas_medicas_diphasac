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
from django.db.models.functions import TruncWeek
from datetime import timedelta
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
    # Mantén tu actualización automática
    actualizar_estados_de_rutas()

    user = request.user

    if user.is_superuser or user.rol == 'supervisor':
        rutas = Ruta.objects.select_related('doctor', 'usuario').order_by('-fecha_visita')
        doctores = Doctor.objects.all()              # Admin/supervisor ven todo
    else:
        rutas = (Ruta.objects
                 .filter(usuario=user)
                 .select_related('doctor')
                 .order_by('-fecha_visita'))
        doctores = Doctor.objects.filter(visitador_id=user.id)  # ← Solo sus médicos

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

@login_required
def ver_historial(request):
    usuario = request.user

    # Query base (sin límites)
    visitas_qs = Visita.objects.filter(usuario=usuario).order_by('-fecha_inicio')
    detalles_qs = DetalleVisita.objects.filter(visita__in=visitas_qs)
    presentados_qs = ProductoPresentado.objects.filter(visita__in=visitas_qs)

    # KPIs
    total_visitas_semana = visitas_qs.filter(
        fecha_inicio__week=timezone.now().isocalendar()[1]
    ).count()
    tiempo_promedio = (visitas_qs
        .exclude(fecha_final=None)
        .annotate(duracion_min=ExpressionWrapper(F('fecha_final') - F('fecha_inicio'), output_field=DurationField()))
        .aggregate(promedio=Avg('duracion_min'))
        .get('promedio') or timedelta(minutes=0)
    )
    total_productos_presentados = presentados_qs.count()
    total_entregas = detalles_qs.count()

    # Datos para gráficos
    visitas_por_semana = (
        visitas_qs.annotate(semana=TruncWeek('fecha_inicio'))
        .values('semana').annotate(total=Count('id')).order_by('semana')
    )
    visitas_semana_labels = [v['semana'].strftime('%d/%m') for v in visitas_por_semana]
    visitas_semana_data = [v['total'] for v in visitas_por_semana]

    productos_por_tipo = (
        detalles_qs.values('producto__tipo_producto')
        .annotate(total=Count('id')).order_by('-total')
    )
    productos_tipo_labels = [p['producto__tipo_producto'] for p in productos_por_tipo] or ["Sin datos"]
    productos_tipo_data = [p['total'] for p in productos_por_tipo] or [1]

    top_doctores = (visitas_qs.values('doctor__nombre')
        .annotate(total=Count('id')).order_by('-total')[:5])
    top_doctores_labels = [d['doctor__nombre'] for d in top_doctores]
    top_doctores_data = [d['total'] for d in top_doctores]

    return render(request, 'visitas/historial.html', {
        # KPIs
        'total_visitas_semana': total_visitas_semana,
        'total_productos_presentados': total_productos_presentados,
        'total_entregas': total_entregas,
        'tiempo_promedio': round(tiempo_promedio.total_seconds() / 60) if tiempo_promedio else 0,

        # Gráficos (JSON)
        'visitas_semana_labels': json.dumps(visitas_semana_labels),
        'visitas_semana_data': json.dumps(visitas_semana_data),
        'productos_tipo_labels': json.dumps(productos_tipo_labels),
        'productos_tipo_data': json.dumps(productos_tipo_data),
        'top_doctores_labels': json.dumps(top_doctores_labels),
        'top_doctores_data': json.dumps(top_doctores_data),

        # Tablas completas (sin límite)
        'visitas': visitas_qs,
        'detalles': detalles_qs,
        'presentados': presentados_qs,
    })