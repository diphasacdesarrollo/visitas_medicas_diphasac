# apps/visitas/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from apps.visitas.models import Visita, DetalleVisita, ProductoPresentado
from apps.productos.models import Producto
from apps.rutas.models import Ruta
from apps.doctores.models import Doctor
from apps.rutas.utils import actualizar_estados_de_rutas

@login_required
def iniciar_visita(request, doctor_id):
    user = request.user
    ubicacion = request.GET.get('ubicacion', '')

    doctor = get_object_or_404(Doctor, id=doctor_id)
    hoy = timezone.now().date()

    ruta_existente = Ruta.objects.filter(doctor=doctor, usuario=user, fecha_visita=hoy).first()
    visita_es_emergencia = False

    if not ruta_existente:
        Ruta.objects.create(
            doctor=doctor,
            usuario=user,
            fecha_visita=hoy,
            estatus='emergencia'
        )
        visita_es_emergencia = True

    # 👇 Esta parte solo ocurre si se envía el formulario
    if request.method == 'POST':
        ubicacion = request.POST.get('ubicacion', '')  # Asegúrate que el name sea "ubicacion" en el input
        visita = Visita.objects.create(
            usuario=user,
            doctor=doctor,
            fecha_inicio=timezone.now(),
            ubicacion_inicio=ubicacion
        )
        request.session['visita_id'] = visita.id
        return redirect('visitas:agregar_productos')

    # 👇 Asegúrate de no pasar 'visita' si no existe
    return render(request, 'visitas/iniciar_visita.html', {
        'doctor': doctor,
        'ubicacion': ubicacion,
        'visita_es_emergencia': visita_es_emergencia
    })

@login_required
def gestionar_visitas_medicas(request):
    # Actualizar automáticamente estatus de rutas antes de mostrar
    actualizar_estados_de_rutas()

    user = request.user

    # Filtrar rutas según el tipo de usuario
    if user.is_superuser or user.rol == 'supervisor':
        rutas = Ruta.objects.select_related('doctor', 'usuario').order_by('-fecha_visita')
        doctores = Doctor.objects.all()  # ✅ Mostrar doctores a supervisores y admin
    else:
        rutas = Ruta.objects.filter(usuario=user).select_related('doctor').order_by('-fecha_visita')
        doctores = Doctor.objects.all()

    return render(request, 'visitas/gestionar_visitas_medicas.html', {
        'rutas': rutas,
        'doctores': doctores,
    })

@login_required
def agregar_productos(request):
    visita_id = request.session.get('visita_id')
    if not visita_id:
        messages.error(request, "No se ha iniciado una visita.")
        return redirect('iniciar_visita')

    visita = get_object_or_404(Visita, id=visita_id)

    if request.method == 'POST':
        accion = request.POST.get('accion')

        # ✅ Guardar productos presentados (checkboxes)
        productos_presentados_ids = request.POST.getlist('productos_presentados')
        ProductoPresentado.objects.filter(visita=visita).exclude(producto_id__in=productos_presentados_ids).delete()
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

            # ✅ Actualizar estado de la ruta
            try:
                ruta = Ruta.objects.get(usuario=request.user, doctor=visita.doctor, fecha_visita=visita.fecha_inicio.date())
                ruta.actualizar_estatus()
            except Ruta.DoesNotExist:
                pass

            del request.session['visita_id']
            messages.success(request, "Visita finalizada correctamente.")
            return redirect('inicio')

    productos_promocionales = Producto.objects.filter(tipo_producto='promocional')
    productos_muestra = Producto.objects.filter(tipo_producto='muestra')
    productos_merch = Producto.objects.filter(tipo_producto='merch')

    productos_presentados = ProductoPresentado.objects.filter(visita=visita).select_related('producto')
    entregas = DetalleVisita.objects.filter(visita=visita).select_related('producto')
    productos_presentados_ids = productos_presentados.values_list('producto_id', flat=True)

    imagen_productos = {
        'DUO DAPHA 10': 'test.jpg',
        'DUO DAPHA 5': 'duo-dapha-5.jpg',
        'DAPHA 10': 'dapha-10.jpg',
        # Añade más imágenes si deseas
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