# -*- coding: utf-8 -*-
# Generated by Django 1.11.14 on 2018-11-06 10:54
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('reports', '0004_drivingstylereportdelivery_faultsreportdelivery'),
    ]

    operations = [
        migrations.CreateModel(
            name='ReportEmailDeliveryLog',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True, verbose_name='Создано')),
                ('updated', models.DateTimeField(auto_now=True, verbose_name='Обновлено')),
                ('email', models.EmailField(max_length=254, verbose_name='Email пользователя')),
                ('report_type', models.CharField(choices=[('faults', 'О состоянии оборудования'), ('driving_style', 'Качество вождения')], max_length=50, verbose_name='Тип отчета')),
                ('report', models.FileField(max_length=255, upload_to='reports/%Y/%m/%d', verbose_name='Отчет')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='email_logs', to=settings.AUTH_USER_MODEL, verbose_name='Пользователь')),
            ],
            options={
                'verbose_name': 'Запись лога рассылки отчетов',
                'verbose_name_plural': 'Лог рассылки отчетов',
                'ordering': ('-created',),
            },
        ),
    ]