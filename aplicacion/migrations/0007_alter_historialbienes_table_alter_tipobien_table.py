# Generated by Django 5.0.6 on 2024-11-11 01:40

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('aplicacion', '0006_remove_usuario_date_joined_remove_usuario_first_name_and_more'),
    ]

    operations = [
        migrations.AlterModelTable(
            name='historialbienes',
            table='historial_bienes',
        ),
        migrations.AlterModelTable(
            name='tipobien',
            table='tipos_bien',
        ),
    ]
