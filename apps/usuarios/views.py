#apps/usuarios/views.py
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect
from .forms import CustomPasswordChangeForm

@login_required
def cambiar_password(request):
    if request.method == 'POST':
        form = CustomPasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            user.must_change_password = False
            user.save()

            messages.success(request, 'Contraseña actualizada con éxito.')
            return redirect('inicio')
        else:
            messages.error(request, 'Corrige los errores a continuación.')
    else:
        form = CustomPasswordChangeForm(request.user)

    return render(request, 'usuarios/cambiar_password.html', {'form': form})

@login_required
def inicio(request):
    return render(request, 'inicio.html')