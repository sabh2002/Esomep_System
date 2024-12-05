# En aplicacion/context_processors.py

from .models import Notificacion

def notificaciones_context(request):
    if request.user.is_authenticated:
        unread_count = Notificacion.objects.filter(usuario=request.user, leida=False).count()
        return {
            'notificaciones_no_leidas': unread_count,
            'has_unread_notifications': unread_count > 0
        }
    return {
        'notificaciones_no_leidas': 0,
        'has_unread_notifications': False
    }