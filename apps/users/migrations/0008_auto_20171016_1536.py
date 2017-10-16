# -*- coding: utf-8 -*-
# Generated by Django 1.11.5 on 2017-10-16 15:36
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0007_user_wialon_geozones_report_template_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='wialon_kmu_report_template_id',
            field=models.BigIntegerField(blank=True, null=True, verbose_name='ID шаблона отчета "Работа крановой установки" в Wialon'),
        ),
        migrations.AlterField(
            model_name='user',
            name='wialon_driving_style_report_template_id',
            field=models.BigIntegerField(blank=True, null=True, verbose_name='ID шаблона отчета "Стиль вождения" в Wialon'),
        ),
        migrations.AlterField(
            model_name='user',
            name='wialon_geozones_report_template_id',
            field=models.BigIntegerField(blank=True, null=True, verbose_name='ID шаблона отчета "Геозоны" в Wialon'),
        ),
    ]