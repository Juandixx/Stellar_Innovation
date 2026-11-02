from functools import wraps

from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import redirect

def es_administrador(user):
    """True si el usuario es superusuario o tiene el rol 'administrador'."""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    perfil = getattr(user, 'usuario', None)
    return bool(perfil and perfil.rol == 'administrador')

def admin_required(view_func):
    """Solo deja pasar a administradores"""
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not es_administrador(request.user):
            messages.error(request, 'No tienes permisos para acceder a esta sección.')
            return redirect('home')
        return view_func(request, *args, **kwargs)
    return _wrapped