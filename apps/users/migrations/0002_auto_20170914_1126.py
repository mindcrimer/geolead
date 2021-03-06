# -*- coding: utf-8 -*-
# Generated by Django 1.11.4 on 2017-09-14 11:26
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='user',
            name='email_verified_date',
        ),
        migrations.RemoveField(
            model_name='user',
            name='restore_salt',
        ),
        migrations.RemoveField(
            model_name='user',
            name='restore_salt_expiry',
        ),
        migrations.AddField(
            model_name='user',
            name='org_id',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='orgId УРА'),
        ),
        migrations.AddField(
            model_name='user',
            name='wialon_token',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='Токен в Wialon'),
        ),
    ]
