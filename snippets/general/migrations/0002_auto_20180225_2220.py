# -*- coding: utf-8 -*-
# Generated by Django 1.11.8 on 2018-02-25 22:20
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('general', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='dbconfig',
            name='created',
            field=models.DateTimeField(auto_now_add=True, verbose_name='Создано'),
        ),
        migrations.AlterField(
            model_name='menu',
            name='created',
            field=models.DateTimeField(auto_now_add=True, verbose_name='Создано'),
        ),
        migrations.AlterField(
            model_name='menuitem',
            name='created',
            field=models.DateTimeField(auto_now_add=True, verbose_name='Создано'),
        ),
    ]