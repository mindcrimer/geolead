# -*- coding: utf-8 -*-
# Generated by Django 1.11.7 on 2017-11-20 10:10
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0011_user_wialon_username'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='organization_name',
            field=models.CharField(blank=True, max_length=255, verbose_name='Название организации в УРА'),
        ),
    ]
