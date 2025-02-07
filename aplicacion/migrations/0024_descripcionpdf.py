# Generated by Django 5.0.6 on 2024-11-21 18:08

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('aplicacion', '0023_alter_movimientosbienes_departamento_destino_id_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='DescripcionPDF',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('descripcion', models.TextField()),
                ('detalles_adicionales', models.JSONField(blank=True, null=True)),
                ('fecha_creacion', models.DateTimeField(auto_now_add=True)),
                ('historial', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='aplicacion.historialbienes')),
            ],
            options={
                'db_table': 'descripciones_pdf',
            },
        ),
    ]
