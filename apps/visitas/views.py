# apps/visitas/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from apps.visitas.models import Visita, DetalleVisita, ProductoPresentado
from apps.productos.models import Producto
from apps.rutas.models import Ruta
from apps.doctores.models import Doctor


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
def agregar_productos(request):
    visita_id = request.session.get('visita_id')
    if not visita_id:
        messages.error(request, "No se ha iniciado una visita.")
        return redirect('iniciar_visita')

    visita = get_object_or_404(Visita, id=visita_id)

    if request.method == 'POST':
        if 'finalizar' in request.POST:
            visita.comentarios = request.POST.get('comentarios', '')
            visita.fecha_final = timezone.now()
            visita.duracion = visita.calcular_duracion()
            visita.save()
            del request.session['visita_id']
            messages.success(request, "Visita finalizada correctamente.")
            return redirect('inicio')

        # ✅ Productos Presentados (checkbox)
        productos_presentados = request.POST.getlist('productos_presentados')
        for prod_id in productos_presentados:
            ProductoPresentado.objects.get_or_create(visita=visita, producto_id=prod_id)

        # ✅ Muestras Médicas y Merch
        producto_id = request.POST.get('producto')
        cantidad = request.POST.get('cantidad')
        tipo_entrega = request.POST.get('tipo_entrega')  # 'muestra' o 'merch'

        if producto_id and cantidad and tipo_entrega:
            DetalleVisita.objects.create(
                visita=visita,
                producto_id=producto_id,
                cantidad=cantidad,
                tipo_entrega=tipo_entrega
            )
            messages.success(request, "Entrega registrada correctamente.")

    # ✅ Separar productos por tipo
    productos_promocionales = Producto.objects.filter(tipo_producto='promocional')
    productos_muestra = Producto.objects.filter(tipo_producto='muestra')
    productos_merch = Producto.objects.filter(tipo_producto='merch')

    productos_presentados = ProductoPresentado.objects.filter(visita=visita).select_related('producto')
    entregas = DetalleVisita.objects.filter(visita=visita).select_related('producto')

    # Mapeo fijo entre nombre del producto y nombre de imagen
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
        'entregas': entregas,
        'imagen_productos': imagen_productos,
    })

@login_required
def gestionar_visitas_medicas(request):
    user = request.user

    # Rutas según tipo de usuario
    if user.is_superuser or user.rol == 'supervisor':
        rutas = Ruta.objects.select_related('doctor', 'usuario').order_by('-fecha_visita')
        doctores = Doctor.objects.all()  # ✅ Mostrar doctores también a admin/supervisor
    else:
        rutas = Ruta.objects.filter(usuario=user).select_related('doctor').order_by('-fecha_visita')
        doctores = Doctor.objects.all()

    return render(request, 'visitas/gestionar_visitas_medicas.html', {
        'rutas': rutas,
        'doctores': doctores
    })