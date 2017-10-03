# -*- coding: utf-8 -*-
# Generated by Django 1.11.4 on 2017-09-14 12:20
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ura', '0002_urajob_route_id'),
    ]

    operations = [
        migrations.AlterField(
            model_name='urajob',
            name='driver_fio',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='ФИО водителя'),
        ),
        migrations.AlterField(
            model_name='urajob',
            name='driver_id',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='idDriver'),
        ),
        migrations.AlterField(
            model_name='urajob',
            name='leave_time',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Дата/время leave'),
        ),
        migrations.AlterField(
            model_name='urajob',
            name='return_time',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Дата/время return'),
        ),
    ]