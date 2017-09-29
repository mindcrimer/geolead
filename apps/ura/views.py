# -*- coding: utf-8 -*-
import random
from datetime import timedelta

from django.db.models import Q
from django.http import HttpResponse

from snippets.utils.datetime import utcnow
from snippets.utils.passwords import generate_random_string
from ura import models
from ura.lib.exceptions import APIProcessError
from ura.lib.resources import URAResource
from ura.lib.response import XMLResponse, error_response
from ura.test_data import SURNAMES_CHOICES, NAMES_CHOICES
from ura.utils import parse_datetime, get_organization_user
from ura.wialon.api import get_drivers_list, get_routes_list, get_units_list
from users.models import User


class URADriversResource(URAResource):
    """Список водителей"""
    @staticmethod
    def post(request, *args, **kwargs):

        doc = request.data.xpath('/driversRequest')
        if len(doc) < 1:
            return error_response(
                'Не найден объект driversRequest', code='driversRequest_not_found'
            )

        doc = doc[0]
        doc_id = doc.get('idDoc', '')
        if not doc_id:
            return error_response('Не указан параметр idDoc', code='idDoc_not_found')

        try:
            org_id = int(doc.get('idOrg', ''))
        except ValueError:
            org_id = 0

        user = get_organization_user(request, org_id)

        try:
            drivers = get_drivers_list(user)
        except APIProcessError as e:
            return error_response(str(e))

        return XMLResponse('ura/drivers.xml', {
            'doc_id': doc_id,
            'create_date': utcnow(),
            'drivers': drivers,
            'org_id': org_id
        })


class URAEchoResource(URAResource):
    """Тест работоспособности сервиса"""
    @staticmethod
    def post(request, *args, **kwargs):

        doc = request.data.xpath('/echoRequest')
        if len(doc) < 1:
            return error_response('Не найден объект echoRequest', code='echoRequest_not_found')

        doc = doc[0]
        doc_id = doc.get('idDoc', '')
        if not doc_id:
            return error_response('Не указан параметр idDoc', code='idDoc_not_found')

        return XMLResponse('ura/echo.xml', {
            'doc_id': doc_id,
            'create_date': utcnow()
        })


class URAJobsSetResource(URAResource):
    model_mapping = {
        'name': ('jobName', str),
        'unit_id':  ('idUnit', str),
        'route_id': ('idRoute', str),
        'driver_id': ('idDriver', str),
        'driver_fio': ('driverFio', str),
        'date_begin': ('dateBegin', parse_datetime),
        'date_end': ('dateEnd', parse_datetime),
        'return_time': ('returnTime', parse_datetime),
        'leave_time': ('leaveTime', parse_datetime)
    }
    model = models.UraJob

    def post(self, request, *args, **kwargs):
        jobs = []
        jobs_els = request.data.xpath('/setJobs/job')

        if jobs_els:

            for j in jobs_els:
                data = {}
                for k, v in self.model_mapping.items():
                    if v[1] == parse_datetime:
                        data[k] = v[1](j.get(v[0]), request.user.ura_tz)
                    else:
                        data[k] = v[1](j.get(v[0]))

                name = data.pop('name')
                if not name:
                    return error_response('Не указан параметр jobName', code='jobName_not_found')

                job = self.model.objects.update_or_create(name=name, defaults=data)[0]
                jobs.append(job)

        result = {
            'now': utcnow(),
            'acceptedJobs': jobs
        }
        return XMLResponse('ura/ackjobs.xml', result)


class URAOrgsResource(URAResource):
    """Получение списка организаций"""
    @staticmethod
    def post(request, *args, **kwargs):

        doc = request.data.xpath('/orgRequest')
        if len(doc) < 1:
            return error_response('Не найден объект orgRequest', code='orgRequest_not_found')

        doc = doc[0]
        doc_id = doc.get('idDoc', '')
        if not doc_id:
            return error_response('Не указан параметр idDoc', code='idDoc_not_found')

        orgs = User.objects\
            .filter(Q(pk=request.user.pk) | Q(supervisor=request.user))\
            .filter(wialon_token__isnull=False, is_active=True)

        return XMLResponse('ura/orgs.xml', {
            'doc_id': doc_id,
            'orgs': orgs,
            'create_date': utcnow()
        })


class URARoutesResource(URAResource):
    """Список маршрутов"""
    @staticmethod
    def post(request, *args, **kwargs):

        doc = request.data.xpath('/routesRequest')
        if len(doc) < 1:
            return error_response('Не найден объект routesRequest', code='routesRequest_not_found')

        doc = doc[0]
        doc_id = doc.get('idDoc', '')
        if not doc_id:
            return error_response('Не указан параметр idDoc', code='idDoc_not_found')

        try:
            org_id = int(doc.get('idOrg', ''))
        except ValueError:
            org_id = 0

        user = get_organization_user(request, org_id)

        try:
            routes = get_routes_list(user)
        except APIProcessError as e:
            return error_response(str(e))

        return XMLResponse('ura/routes.xml', {
            'doc_id': doc_id,
            'create_date': utcnow(),
            'routes': routes,
            'org_id': org_id
        })


class URAUnitsResource(URAResource):
    """Список элементов"""
    @staticmethod
    def post(request, *args, **kwargs):

        doc = request.data.xpath('/unitsRequest')
        if len(doc) < 1:
            return error_response('Не найден объект unitsRequest', code='unitsRequest_not_found')

        doc = doc[0]
        doc_id = doc.get('idDoc', '')
        if not doc_id:
            return error_response('Не указан параметр idDoc', code='idDoc_not_found')

        try:
            org_id = int(doc.get('idOrg', ''))
        except ValueError:
            org_id = 0

        user = get_organization_user(request, org_id)

        try:
            units = get_units_list(user)
        except APIProcessError as e:
            return error_response(str(e))

        return XMLResponse('ura/units.xml', {
            'doc_id': doc_id,
            'create_date': utcnow(),
            'units': units,
            'org_id': org_id
        })


class URAJobsTestDataView(URAResource):
    @staticmethod
    def generate_fio():
        last_name = random.choice(SURNAMES_CHOICES)
        first_name = random.choice(NAMES_CHOICES).upper()
        middle_name = random.choice(NAMES_CHOICES).upper()
        return '%s %s.%s' % (last_name, first_name, middle_name)

    @classmethod
    def post(cls, request, *args, **kwargs):
        try:
            units = get_units_list(request.user)
        except APIProcessError as e:
            return error_response(str(e))

        try:
            routes = get_routes_list(request.user)
        except APIProcessError as e:
            return error_response(str(e))

        if not routes:
            routes = [{
                'id': 1,
                'name': 'test route'
            }]
        now = utcnow().replace(hour=0, minute=0, second=0)
        dt = utcnow() - timedelta(days=30)
        delta = timedelta(seconds=60 * 60 * 8)

        drivers = [cls.generate_fio() for _ in range(50)]

        periods = []
        while dt < now:
            dt += delta
            periods.append(dt)

        for dt in periods:
            to_dt = dt + delta
            print(dt, to_dt)

            for unit in units:
                fio = random.choice(drivers)
                print(fio)
                route = random.choice(routes)

                models.UraJob.objects.create(
                    name=generate_random_string(),
                    unit_id=unit['id'],
                    route_id=route['id'],
                    driver_id=random.randint(1, 1000000),
                    driver_fio=fio,
                    date_begin=dt,
                    date_end=to_dt,
                    return_time=to_dt,
                    leave_time=dt
                )

        return HttpResponse('OK')


class URAJobsBreakResource(URAResource):
    model_mapping = {
        'date_begin': ('dateBegin', parse_datetime),
        'date_end': ('dateEnd', parse_datetime),
        'return_time': ('returnTime', parse_datetime),
        'leave_time': ('leaveTime', parse_datetime)
    }
    model = models.UraJob

    def post(self, request, *args, **kwargs):
        jobs = []
        jobs_els = request.data.xpath('/breakJobs/job')

        if jobs_els:

            for j in jobs_els:
                data = {}
                for k, v in self.model_mapping.items():
                    if v[1] == parse_datetime:
                        data[k] = v[1](j.get(v[0]), request.user.ura_tz)
                    else:
                        data[k] = v[1](j.get(v[0]))

                name = data.pop('name')
                if not name:
                    return error_response('Не указан параметр jobName', code='jobName_not_found')

                if data['date_end'] <= data['date_begin']:
                    self.model.objects.filter(name=name).delete()
                else:
                    job = self.model.objects.filter(name=name).update(**data)
                    jobs.append(job)

        result = {
            'now': utcnow(),
            'breakJobs': jobs
        }
        return XMLResponse('ura/ackBreakJobs.xml', result)


class URARacesResource(URAResource):
    def post(self, request, *args, **kwargs):
        jobs = []
        jobs_els = request.data.xpath('/getRaces/job')

        if jobs_els:

            for j in jobs_els:
                data = {}
                for k, v in self.model_mapping.items():
                    if v[1] == parse_datetime:
                        data[k] = v[1](j.get(v[0]), request.user.ura_tz)
                    else:
                        data[k] = v[1](j.get(v[0]))

                name = data.pop('name')
                if not name:
                    return error_response('Не указан параметр jobName', code='jobName_not_found')

                job = self.model.objects.update_or_create(name=name, defaults=data)[0]
                jobs.append(job)

        result = {
            'now': utcnow(),
            'units': jobs
        }
        return XMLResponse('ura/races.xml', result)


class URAMovingResource(URAResource):
    def post(self, request, *args, **kwargs):
        units = []
        units_els = request.data.xpath('/getMoving/unit')

        if units_els:
            pass

        result = {
            'now': utcnow(),
            'units': units
        }
        return XMLResponse('ura/moving.xml', result)
