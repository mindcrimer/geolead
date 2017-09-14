# -*- coding: utf-8 -*-
from snippets.utils.datetime import utcnow
from ura import models
from ura.lib.resources import URAResource
from ura.lib.response import XMLResponse, error_response
from ura.utils import parse_datetime


class URAEchoResource(URAResource):
    @staticmethod
    def post(request, *args, **kwargs):

        echo = request.data.xpath('/echoRequest')
        if len(echo) < 1:
            return error_response('Не найден объект echoRequest')

        echo = echo[0]
        doc_id = echo.get('idDoc')
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
