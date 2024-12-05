from __future__ import absolute_import, unicode_literals
import os
from celery import Celery

# Establecer la variable de entorno DJANGO_SETTINGS_MODULE
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'proyecto.settings')

app = Celery('proyecto')

# Usar la configuración de Django para la configuración de Celery
app.config_from_object('django.conf:settings', namespace='CELERY')

# Cargar tareas de todos los módulos registrados en INSTALLED_APPS
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')