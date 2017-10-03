# -*- coding: utf-8 -*-
# Generated by Django 1.11.5 on 2017-09-26 19:37
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0005_auto_20170921_1000'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='wialon_discharge_report_template_id',
            field=models.BigIntegerField(blank=True, null=True, verbose_name='ID отчета "Перерасход топлива" в Wialon'),
        ),
        migrations.AddField(
            model_name='user',
            name='wialon_driving_style_report_template_id',
            field=models.BigIntegerField(blank=True, null=True, verbose_name='ID отчета "Стиль вождения" в Wialon'),
        ),
        migrations.AddField(
            model_name='user',
            name='wialon_report_object_id',
            field=models.BigIntegerField(blank=True, null=True, verbose_name='ID группового объекта для отчетов в Wialon'),
        ),
        migrations.AddField(
            model_name='user',
            name='wialon_report_resource_id',
            field=models.BigIntegerField(blank=True, null=True, verbose_name='ID ресурса отчетов в Wialon'),
        ),
    ]