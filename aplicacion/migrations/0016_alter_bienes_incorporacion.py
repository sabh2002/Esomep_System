# Generated by Django 5.0.6 on 2024-11-18 03:59

import django.core.validators
from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('aplicacion', '0015_alter_bienes_desincorporacion_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='bienes',
            name='incorporacion',
            field=models.DecimalField(decimal_places=2, default=Decimal('0.00'), help_text='Valor en bolívares', max_digits=20, validators=[django.core.validators.MinValueValidator(Decimal('0.00'))]),
        ),
    ]
