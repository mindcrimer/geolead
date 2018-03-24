# -*- coding: utf-8 -*-
# Generated by Django 1.11.8 on 2018-03-19 00:32
from __future__ import unicode_literals

import django.contrib.postgres.fields.jsonb
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('ura', '0019_auto_20180227_0941'),
    ]

    operations = [
        migrations.CreateModel(
            name='Event',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True, verbose_name='Создано')),
                ('updated', models.DateTimeField(auto_now=True, verbose_name='Обновлено')),
            ],
            options={
                'verbose_name_plural': 'События',
                'verbose_name': 'Событие',
            },
        ),
        migrations.CreateModel(
            name='Notification',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True, verbose_name='Создано')),
                ('updated', models.DateTimeField(auto_now=True, verbose_name='Обновлено')),
                ('wialon_id', models.IntegerField(verbose_name='ID в Wialon')),
                ('sent_data', django.contrib.postgres.fields.jsonb.JSONField(blank=True, verbose_name='Данные отправленные')),
                ('received_data', django.contrib.postgres.fields.jsonb.JSONField(blank=True, verbose_name='Данные полученные')),
                ('job', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notifications', to='ura.Job', verbose_name='Путевой лист')),
            ],
            options={
                'verbose_name_plural': 'Шаблоны уведомлений',
                'verbose_name': 'Шаблон уведомления',
            },
        ),
        migrations.AddField(
            model_name='event',
            name='notification',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='events', to='notifications.Notification', verbose_name='Шаблон уведомления'),
        ),
    ]