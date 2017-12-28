# -*- coding: utf-8 -*-
# Generated by Django 1.11.8 on 2017-12-21 16:30
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ura', '0012_urajoblog_user'),
    ]

    operations = [
        migrations.AddField(
            model_name='urajoblog',
            name='resolution',
            field=models.SmallIntegerField(choices=[(None, 'Не рассмотрено'), (100, 'Подтверждено'), (-100, 'Отклонено')], default=None, null=True, verbose_name='Резолюция ошибки'),
        ),
        migrations.AddField(
            model_name='urajoblog',
            name='url',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='URL'),
        ),
    ]