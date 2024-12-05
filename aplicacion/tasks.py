from celery import shared_task
from django.utils import timezone
from .models import Solicitudes, Notificacion, Usuario

@shared_task
def verificar_solicitudes_temporales():
    solicitudes_expiradas = Solicitudes.objects.filter(
        id_tipos_de_solicitud__nombre='Temporal',
        estado_solicitud='aprobada',
        fecha_maxima_traslado__lt=timezone.now()
    )
    
    admin_users = Usuario.objects.filter(id_rol_del_usuario__nombre_rol='ADMIN_BIENES')
    
    for solicitud in solicitudes_expiradas:
        for admin in admin_users:
            Notificacion.objects.create(
                usuario=admin,
                mensaje=f"La solicitud temporal {solicitud.id_solicitudes} ha expirado. Bien: {solicitud.bien_id.nombre}, Usuario: {solicitud.usuario_id.username}"
            )
        
        # Cambiar el estado de la solicitud a 'expirada'
        solicitud.estado_solicitud = 'expirada'
        solicitud.save()