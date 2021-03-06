# -*- coding: utf-8 -*-
# Generated by Django 1.11.8 on 2018-03-18 22:19
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import snippets.utils.passwords


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('reports', '0002_auto_20180318_2218'),
    ]

    operations = [
        migrations.CreateModel(
            name='Report',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True, verbose_name='Создано')),
                ('updated', models.DateTimeField(auto_now=True, verbose_name='Обновлено')),
                ('uid', models.CharField(default=snippets.utils.passwords.generate_uuid4, max_length=36, unique=True, verbose_name='Идентификатор')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='report_logs', to=settings.AUTH_USER_MODEL, verbose_name='Пользователь')),
            ],
            options={
                'verbose_name': 'Отчет',
                'verbose_name_plural': 'Отчеты',
            },
        ),
        migrations.CreateModel(
            name='ReportLog',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True, verbose_name='Создано')),
                ('updated', models.DateTimeField(auto_now=True, verbose_name='Обновлено')),
                ('log_message', models.TextField(blank=True, verbose_name='Сообщение')),
                ('report', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='logs', to='reports.Report', verbose_name='Отчет')),
            ],
            options={
                'verbose_name': 'Запись лога отчетов',
                'verbose_name_plural': 'Логи отчетов',
            },
        ),
        migrations.AlterModelOptions(
            name='wialonreportlog',
            options={'verbose_name': 'Выполнение отчета', 'verbose_name_plural': 'Счетчик выполнения отчетов в Wialon'},
        ),
        migrations.AlterField(
            model_name='wialonreportlog',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='wialon_report_logs', to=settings.AUTH_USER_MODEL, verbose_name='Пользователь'),
        ),
    ]
