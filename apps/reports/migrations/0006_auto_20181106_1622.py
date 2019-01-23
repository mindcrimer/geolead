# -*- coding: utf-8 -*-
# Generated by Django 1.11.14 on 2018-11-06 16:22
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reports', '0005_reportemaildeliverylog'),
    ]

    operations = [
        migrations.AddField(
            model_name='drivingstylereportdelivery',
            name='is_daily',
            field=models.BooleanField(default=True, verbose_name='Ежедневный отчет'),
        ),
        migrations.AddField(
            model_name='drivingstylereportdelivery',
            name='is_monthly',
            field=models.BooleanField(default=True, verbose_name='Ежемесячный отчет'),
        ),
        migrations.AddField(
            model_name='drivingstylereportdelivery',
            name='is_weekly',
            field=models.BooleanField(default=True, verbose_name='Еженедельный отчет'),
        ),
    ]