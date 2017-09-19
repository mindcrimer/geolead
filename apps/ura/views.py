# -*- coding: utf-8 -*-
from django.db.models import Q

from snippets.utils.datetime import utcnow
from ura import models
from ura.lib.resources import URAResource
from ura.lib.response import XMLResponse, error_response
from ura.utils import parse_datetime, get_organization
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

        organization = get_organization(request, org_id)

        drivers = get_drivers_list(organization)

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


class URAJobsResource(URAResource):
    model_mapping = {
        'name': ('jobName', str),
        'unit_id':  ('idUnit', int),
        'route_id': ('idRoute', int),
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

        organization = get_organization(request, org_id)

        routes = get_routes_list(organization)

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

        organization = get_organization(request, org_id)

        units = get_units_list(organization)

        return XMLResponse('ura/units.xml', {
            'doc_id': doc_id,
            'create_date': utcnow(),
            'units': units,
            'org_id': org_id
        })
