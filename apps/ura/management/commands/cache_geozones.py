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
                    defaults={'title': name}
                )

                if not created and job_template.title != name:
                    job_template.title = name
                    job_template.save()

                print('%s points found' % len(route['points']))
                for point in route['points']:
                    name = point['name'].strip()
                    standard_point, created = StandardPoint.objects.get_or_create(
                        job_template=job_template,
                        wialon_id=str(point['id']),
                        defaults={'title': name}
                    )

                    if not created and standard_point.title != name:
                        standard_point.title = name
                        standard_point.save()

            sleep(.5)
            i += 1


class Command(BaseCommand):
    def handle(self, *args, **options):
        return cache_geozones()
