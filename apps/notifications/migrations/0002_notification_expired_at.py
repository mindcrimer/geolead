# -*- coding: utf-8 -*-
# Generated by Django 1.11.8 on 2018-03-20 21:39
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='notification',
            name='expired_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Срок жизни'),
        ),
    ]
