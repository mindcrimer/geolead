# -*- coding: utf-8 -*-
# Generated by Django 1.11.8 on 2018-06-12 14:04
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('ura', '0019_auto_20180227_0941'),
    ]

    operations = [
        migrations.AlterField(
            model_name='job',
            name='user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='jobs', to=settings.AUTH_USER_MODEL, verbose_name='Организация'),
        ),
        migrations.AlterField(
            model_name='joblog',
            name='job',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='log', to='ura.Job', verbose_name='Путевой лист'),
        ),
        migrations.AlterField(
            model_name='joblog',
            name='user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='logs', to=settings.AUTH_USER_MODEL, verbose_name='Пользователь'),
        ),
        migrations.AlterField(
            model_name='standardjobtemplate',
            name='user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='standard_job_templates', to=settings.AUTH_USER_MODEL, verbose_name='Пользователь'),
        ),
    ]
