# Generated by Django 5.0.6 on 2024-11-15 14:59

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('aplicacion', '0012_alter_bienes_desincorporacion_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='usuario',
            name='fecha_bloqueo',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='usuario',
            name='fecha_eliminacion',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
