# -*- coding: utf-8 -*-
# Generated by Django 1.11.8 on 2018-06-29 10:25
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ura', '0021_auto_20180613_1404'),
    ]

    operations = [
        migrations.AddField(
            model_name='standardpoint',
            name='mileage_standard',
            field=models.FloatField(blank=True, null=True, verbose_name='Норматив пробега, км'),
        ),
    ]
