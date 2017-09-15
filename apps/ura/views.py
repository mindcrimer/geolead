# -*- coding: utf-8 -*-
from snippets.utils.datetime import utcnow
from ura import models
from ura.lib.resources import URAResource
from ura.lib.response import XMLResponse, error_response
from ura.utils import parse_datetime
from ura.wialon.api import get_drivers_list


class URADriversResource(URAResource):
    """Список водителей"""
    @staticmethod
    def post(request, *args, **kwargs):

        doc = request.data.xpath('/driversRequest')
        if len(doc) < 1:
            return error_response('Не найден объект driversRequest')

        doc = doc[0]
        doc_id = doc.get('idDoc')
        if not doc_id:
            return error_response('Не указан параметр idDoc')

        try:
            org_id = int(doc.get('idOrg'))
        except ValueError:
            org_id = 0

        if not org_id:
            return error_response('Не указан параметр idOrg')

        if org_id != request.user.id:
            return error_response(
                'Параметр idOrg не соответствует идентификатору текущего пользователя'
            )

        drivers = get_drivers_list(request)

        return XMLResponse('ura/drivers.xml', {
            'doc_id': doc_id,
            'create_date': utcnow(),
            'drivers': drivers,
            'org': request.user
        })


class URAEchoResource(URAResource):
    """Тест работоспособности сервиса"""
    @staticmethod
    def post(request, *args, **kwargs):

        doc = request.data.xpath('/echoRequest')
        if len(doc) < 1:
            return error_response('Не найден объект echoRequest')

        doc = doc[0]
        doc_id = doc.get('idDoc')
        if not doc_id:
            return error_response('Не указан параметр idDoc')

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
                    return error_response('Не указан параметр jobName')

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
            return error_response('Не найден объект mon:orgRequest')

        doc = doc[0]
        doc_id = doc.get('idDoc')
        if not doc_id:
            return error_response('Не указан параметр idDoc')

        return XMLResponse('ura/orgs.xml', {
            'doc_id': doc_id,
            'org': request.user,
            'create_date': utcnow()
        })
