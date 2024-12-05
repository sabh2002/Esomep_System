from django.core.management.base import BaseCommand
from aplicacion.models import Bien  # Asegúrate de reemplazar 'aplicacion' con el nombre real de tu aplicación

class Command(BaseCommand):
    help = 'Actualiza todos los bienes sin estado a estado "activo"'

    def handle(self, *args, **options):
        bienes_actualizados = Bien.objects.filter(estado_actual__isnull=True).update(estado_actual='activo')
        self.stdout.write(self.style.SUCCESS(f'Se actualizaron {bienes_actualizados} bienes a estado "activo"'))