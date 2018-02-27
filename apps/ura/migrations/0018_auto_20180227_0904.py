# -*- coding: utf-8 -*-
# Generated by Django 1.11.8 on 2018-02-27 09:04
from __future__ import unicode_literals

from django.db import migrations, models

from wialon.api import get_units, get_routes


def forwards_func(apps, schema_editor):
    job_model = apps.get_model('ura', 'UraJob')
    user_model = apps.get_model('users', 'User')

    orgs = user_model.objects.filter(is_active=True, supervisor__isnull=False)
    units_cache ={}
    routes_cache = {}

    for org in orgs.iterator():
        print('Organization %s' % org.username)
        units = get_units(user=org)
        units_cache[org.pk] = {
            u['id']: '%s (%s) [%s]' % (u['name'], u['number'], u['vin']) for u in units
        }

        routes = get_routes(user=org)
        routes_cache[org.pk] = {r['id']: r['name'] for r in routes}

    print('Jobs count: %s' % job_model.objects.count())

    i = 0
    for job in job_model.objects.iterator():
        i += 1
        if not job.user_id:
            print('%s: Job %s missed due to lack of user' % (i, job.pk))
            continue

        unit_title = route_title = None

        try:
            unit_id = int(job.unit_id)
            unit_title = units_cache.get(job.user_id, {}).get(unit_id)
            if unit_title:
                job.unit_title = unit_title
        except (ValueError, TypeError, AttributeError):
            pass

        try:
            route_id = int(job.route_id)
            route_title = routes_cache.get(job.user_id, {}).get(route_id)
            if route_title:
                job.route_title = route_title
        except (ValueError, TypeError, AttributeError):
            pass

        if unit_title or route_title:
            job.save()

        print('%s: unit=%s, route=%s (%s)' % (i, unit_title, route_title, job.created))


def backwards_func(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('ura', '0017_auto_20180225_2220'),
    ]

    operations = [
        migrations.AddField(
            model_name='urajob',
            name='route_title',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='Название маршрута'),
        ),
        migrations.AddField(
            model_name='urajob',
            name='unit_title',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='Название объекта (ТС)'),
        ),
        migrations.AlterField(
            model_name='urajob',
            name='date_begin',
            field=models.DateTimeField(verbose_name='Время начала ПЛ'),
        ),
        migrations.AlterField(
            model_name='urajob',
            name='date_end',
            field=models.DateTimeField(verbose_name='Время окончания ПЛ'),
        ),
        migrations.AlterField(
            model_name='urajob',
            name='driver_id',
            field=models.CharField(blank=True, max_length=100, null=True, verbose_name='ID водителя'),
        ),
        migrations.AlterField(
            model_name='urajob',
            name='leave_time',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Время выезда'),
        ),
        migrations.AlterField(
            model_name='urajob',
            name='return_time',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Время заезда'),
        ),
        migrations.AlterField(
            model_name='urajob',
            name='route_id',
            field=models.CharField(max_length=100, verbose_name='ID маршрута'),
        ),
        migrations.AlterField(
            model_name='urajob',
            name='unit_id',
            field=models.CharField(max_length=100, verbose_name='ID объекта (ТС)'),
        ),
        migrations.RunPython(forwards_func, backwards_func)
    ]
