# -*- coding: utf-8 -*-
# Generated by Django 1.11.8 on 2018-03-05 17:01
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0023_auto_20180302_0748'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='wialon_discharge_individual_report_template_name',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='Наименование отчета "Перерасход топлива индивидуальный"'),
        ),
    ]