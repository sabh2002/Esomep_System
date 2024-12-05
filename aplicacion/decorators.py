from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.core.exceptions import PermissionDenied

def role_required(allowed_roles=[]):
    """
    Decorador que verifica si el usuario tiene uno de los roles permitidos.
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if request.user.is_authenticated and request.user.id_rol_del_usuario and request.user.id_rol_del_usuario.nombre_rol in allowed_roles:
                return view_func(request, *args, **kwargs)
            messages.error(request, "No tiene permisos para acceder a esta sección.")
            return redirect('home')
        return wrapper
    return decorator

def es_admin_bienes(user):
    """
    Verifica si el usuario es administrador de bienes.
    """
    return user.is_authenticated and user.id_rol_del_usuario and user.id_rol_del_usuario.nombre_rol == 'ADMIN_BIENES'

def user_passes_test(test_func):
    """
    Decorador que verifica si el usuario pasa el test proporcionado.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if test_func(request.user):
                return view_func(request, *args, **kwargs)
            messages.error(request, "No tiene permisos para acceder a esta sección.")
            return redirect('home')
        return _wrapped_view
    return decorator

def admin_bienes_required(function):
    """
    Decorador específico para vistas que requieren rol de administrador de bienes.
    """
    @wraps(function)
    def wrap(request, *args, **kwargs):
        if es_admin_bienes(request.user):
            return function(request, *args, **kwargs)
        messages.error(request, "Acceso restringido a Administradores de Bienes.")
        return redirect('home')
    return wrap
