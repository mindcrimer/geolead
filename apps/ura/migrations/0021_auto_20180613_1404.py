# -*- coding: utf-8 -*-
# Generated by Django 1.11.8 on 2018-06-13 14:04
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion
from django.db.models import F


def forwards_func(apps, schema_editor):
    apps.get_model('ura', 'JobPoint').objects.update(move_time=F('total_time') - F('parking_time'))


def backwards_func(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('ura', '0020_auto_20180612_1404'),
    ]

    operations = [
        migrations.CreateModel(
            name='JobPointStop',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True, verbose_name='Создано')),
                ('updated', models.DateTimeField(auto_now=True, verbose_name='Обновлено')),
                ('start_date_time', models.DateTimeField(blank=True, null=True, verbose_name='Время начала')),
                ('finish_date_time', models.DateTimeField(blank=True, null=True, verbose_name='Время конца')),
                ('place', models.TextField(blank=True, verbose_name='Местоположение')),
                ('lat', models.FloatField(blank=True, null=True, verbose_name='Широта точки остановки')),
                ('lng', models.FloatField(blank=True, null=True, verbose_name='Долгота точки остановки')),
            ],
            options={
                'verbose_name': 'Остановка по маршруту ПЛ',
                'verbose_name_plural': 'Остановки по маршруту ПЛ',
            },
        ),
        migrations.AddField(
            model_name='jobpoint',
            name='gpm_time',
            field=models.FloatField(blank=True, null=True, verbose_name='Время работы ГПМ, сек'),
        ),
        migrations.AddField(
            model_name='jobpoint',
            name='motohours_time',
            field=models.FloatField(blank=True, null=True, verbose_name='Время работающего двигателя, сек'),
        ),
        migrations.AddField(
            model_name='jobpoint',
            name='move_time',
            field=models.FloatField(blank=True, null=True, verbose_name='Время движения в геозоне, сек'),
        ),
        migrations.AddField(
            model_name='jobpointstop',
            name='job_point',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='stops', to='ura.JobPoint', verbose_name='Геозона путевого листа'),
        ),
        migrations.RunPython(forwards_func, backwards_func)
    ]
