# -*- coding: utf-8 -*-
from time import sleep

from django.core.management.base import BaseCommand
from django.db import transaction

from ura.models import StandardJobTemplate, StandardPoint
from users.models import User
from wialon.api import get_routes


def cache_geozones():
    print('Caching geozones...')

    with transaction.atomic():
        i = 1
        users = User.objects.filter(
            supervisor__isnull=False, wialon_username__isnull=False, wialon_password__isnull=False
        ).exclude(wialon_username='', wialon_password='')

        print('%s users found' % len(users))

        for user in users:
            print('%s) User %s processing' % (i, user))

            routes = get_routes(user=user, with_points=True)
            print('%s routes found' % len(routes))

            for route in routes:
                print('Route %s' % route['name'])

                name = route['name'].strip()
                job_template, created = StandardJobTemplate.objects.get_or_create(
                    wialon_id=str(route['id']),
                    defaults={
                        'title': name,
                        'user': user
                    }
                )

                existing_points = set()
                if not created:
                    if job_template.title != name:
                        job_template.title = name
                    job_template.user = user
                    job_template.save()

                    existing_points = {p for p in job_template.points.all()}

                # убираем дубли (когда одна и та же геозона дублируется в маршруте)
                route['points'] = {r['id']: r for r in route['points']}.values()

                print('%s points found, already exist: %s' % (
                    len(route['points']), len(existing_points)
                ))

                for point in route['points']:
                    name = point['name'].strip()
                    standard_point, created = StandardPoint.objects.get_or_create(
                        job_template=job_template,
                        wialon_id=str(point['id']),
                        defaults={'title': name}
                    )

                    if not created:
                        existing_points.discard(standard_point)

                        if standard_point.title != name:
                            standard_point.title = name
                            standard_point.save()

                if existing_points:
                    print('Points to remove: %s' % ', '.join([str(x) for x in existing_points]))
                    for existing_point in existing_points:
                        existing_point.delete()

            sleep(.3)
            i += 1


class Command(BaseCommand):
    def handle(self, *args, **options):
        return cache_geozones()
