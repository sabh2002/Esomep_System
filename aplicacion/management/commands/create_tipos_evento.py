from django.core.management.base import BaseCommand
from aplicacion.models import TiposDeEvento

class Command(BaseCommand):
    help = 'Crea el tipo de evento para Cambio de Ubicación'

    def handle(self, *args, **kwargs):
        TiposDeEvento.objects.get_or_create(
            nombre="Cambio de Ubicación",
            defaults={'descripcion': 'Evento que registra el cambio de ubicación de un bien'}
        )
        self.stdout.write(self.style.SUCCESS('Tipo de evento "Cambio de Ubicación" creado exitosamente'))