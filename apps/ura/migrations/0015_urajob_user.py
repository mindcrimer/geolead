# -*- coding: utf-8 -*-
# Generated by Django 1.11.8 on 2017-12-29 09:44
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('ura', '0014_auto_20171228_2017'),
    ]

    operations = [
        migrations.AddField(
            model_name='urajob',
            name='user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='jobs', to=settings.AUTH_USER_MODEL, verbose_name='Организация'),
        ),
    ]
