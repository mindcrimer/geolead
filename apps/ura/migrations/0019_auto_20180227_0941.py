# -*- coding: utf-8 -*-
# Generated by Django 1.11.8 on 2018-02-27 09:41
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ura', '0018_auto_20180227_0904'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='UraJob',
            new_name='Job',
        ),
        migrations.RenameModel(
            old_name='UraJobLog',
            new_name='JobLog',
        ),
        migrations.RenameModel(
            old_name='UraJobPoint',
            new_name='JobPoint',
        ),
    ]
