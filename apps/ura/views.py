# -*- coding: utf-8 -*-
import datetime
import random

from django.db.models import Q
from django.http import HttpResponse

from base.exceptions import APIProcessError, ReportException
from reports.utils import get_period, get_wialon_geozones_report_template_id, \
    cleanup_and_request_report, exec_report, get_report_rows
from snippets.utils.datetime import utcnow
from snippets.utils.passwords import generate_random_string
from ura import models
from ura.lib.resources import URAResource
from ura.lib.response import XMLResponse, error_response
from ura.test_data import SURNAMES_CHOICES, NAMES_CHOICES
from ura.utils import parse_datetime, get_organization_user, parse_xml_input_data
from ura.wialon.api import get_drivers_list, get_routes_list, get_units_list
from ura.wialon.auth import authenticate_at_wialon
from users.models import User


class URADriversResource(URAResource):
    """Список водителей"""
    def post(self, request, *args, **kwargs):

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

        context = self.get_context_data(**kwargs)
        context.update({
            'doc_id': doc_id,
            'create_date': utcnow(),
            'drivers': drivers,
            'org_id': org_id
        })

        return XMLResponse('ura/drivers.xml', context)


class URAEchoResource(URAResource):
    """Тест работоспособности сервиса"""
    def post(self, request, *args, **kwargs):

        doc = request.data.xpath('/echoRequest')
        if len(doc) < 1:
            return error_response('Не найден объект echoRequest', code='echoRequest_not_found')

        doc = doc[0]
        doc_id = doc.get('idDoc', '')
        if not doc_id:
            return error_response('Не указан параметр idDoc', code='idDoc_not_found')

        context = self.get_context_data(**kwargs)
        context.update({
            'doc_id': doc_id,
            'create_date': utcnow()
        })
        return XMLResponse('ura/echo.xml', context)


class URAOrgsResource(URAResource):
    """Получение списка организаций"""
    def post(self, request, *args, **kwargs):

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

        context = self.get_context_data(**kwargs)
        context.update({
            'doc_id': doc_id,
            'orgs': orgs,
            'create_date': utcnow()
        })

        return XMLResponse('ura/orgs.xml', context)


class URARoutesResource(URAResource):
    """Список маршрутов"""
    def post(self, request, *args, **kwargs):

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

        context = self.get_context_data(**kwargs)
        context.update({
            'doc_id': doc_id,
            'create_date': utcnow(),
            'routes': routes,
            'org_id': org_id
        })

        return XMLResponse('ura/routes.xml', context)


class URAUnitsResource(URAResource):
    """Список элементов"""
    def post(self, request, *args, **kwargs):

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

        context = self.get_context_data(**kwargs)
        context.update({
            'doc_id': doc_id,
            'create_date': utcnow(),
            'units': units,
            'org_id': org_id
        })

        return XMLResponse('ura/units.xml', context)


# class URAJobsTestDataView(URAResource):
#     @staticmethod
#     def generate_fio():
#         last_name = random.choice(SURNAMES_CHOICES)
#         first_name = random.choice(NAMES_CHOICES).upper()
#         middle_name = random.choice(NAMES_CHOICES).upper()
#         return '%s %s.%s' % (last_name, first_name, middle_name)
#
#     @classmethod
#     def post(cls, request, *args, **kwargs):
#         try:
#             units = get_units_list(request.user)
#         except APIProcessError as e:
#             return error_response(str(e))
#
#         try:
#             routes = get_routes_list(request.user)
#         except APIProcessError as e:
#             return error_response(str(e))
#
#         if not routes:
#             routes = [{
#                 'id': 1,
#                 'name': 'test route'
#             }]
#         now = utcnow().replace(hour=0, minute=0, second=0)
#         dt = utcnow() - datetime.timedelta(days=30)
#         delta = datetime.timedelta(seconds=60 * 60 * 8)
#
#         drivers = [cls.generate_fio() for _ in range(50)]
#
#         periods = []
#         while dt < now:
#             dt += delta
#             periods.append(dt)
#
#         for dt in periods:
#             to_dt = dt + delta
#             print(dt, to_dt)
#
#             for unit in units:
#                 fio = random.choice(drivers)
#                 print(fio)
#                 route = random.choice(routes)
#
#                 models.UraJob.objects.create(
#                     name=generate_random_string(),
#                     unit_id=unit['id'],
#                     route_id=route['id'],
#                     driver_id=random.randint(1, 1000000),
#                     driver_fio=fio,
#                     date_begin=dt,
#                     date_end=to_dt,
#                     return_time=to_dt,
#                     leave_time=dt
#                 )
#
#         return HttpResponse('OK')


class URASetJobsResource(URAResource):
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
                data = parse_xml_input_data(request, self.model_mapping, j)

                name = data.pop('name')
                if not name:
                    return error_response('Не указан параметр jobName', code='jobName_not_found')

                job = self.model.objects.update_or_create(name=name, defaults=data)[0]
                jobs.append(job)

        context = self.get_context_data(**kwargs)
        context.update({
            'now': utcnow(),
            'acceptedJobs': jobs
        })

        return XMLResponse('ura/ackjobs.xml', context)


class URABreakJobsResource(URAResource):
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
                data = parse_xml_input_data(request, self.model_mapping, j)

                name = data.pop('name')
                if not name:
                    return error_response('Не указан параметр jobName', code='jobName_not_found')

                if data['date_end'] <= data['date_begin']:
                    self.model.objects.filter(name=name).delete()
                else:
                    job = self.model.objects.filter(name=name).update(**data)
                    jobs.append(job)

        context = self.get_context_data(**kwargs)
        context.update({
            'now': utcnow(),
            'breakJobs': jobs
        })

        return XMLResponse('ura/ackBreakJobs.xml', context)


class URARacesResource(URAResource):
    model_mapping = {
        'date_begin': ('dateBegin', parse_datetime),
        'date_end': ('dateEnd', parse_datetime),
        'return_time': ('returnTime', parse_datetime),
        'leave_time': ('leaveTime', parse_datetime),
        'job_id': ('idJob', int),
        'unit_id': ('idUnit', str),
        'route_id': ('idRoute', str),
    }

    def post(self, request, *args, **kwargs):
        jobs = []

        context = self.get_context_data(**kwargs)
        context.update({
            'now': utcnow(),
            'jobs': jobs
        })

        sess_id = authenticate_at_wialon(request.user.wialon_token)
        # units_list = get_units_list(sess_id=sess_id, extra_fields=True)
        # units_dict = {x['id']: x for x in units_list}

        jobs_els = request.data.xpath('/getRaces/job')

        if not jobs_els:
            return error_response('Не указаны объекты типа job', code='jobs_not_found')

        for j in jobs_els:
            data = parse_xml_input_data(request, self.model_mapping, j)

            try:
                job = data['job'] = models.UraJob.objects.get(pk=data['job_id'])
            except models.UraJob.DoesNotExist:
                return error_response('Заявка не найдена', code='job_not_found')

            unit_id = data.get('unit_id', job.unit_id)

            dt_from, dt_to = get_period(
                data['date_begin'],
                data['date_end'],
                request.user.ura_tz
            )

            cleanup_and_request_report(
                request.user,
                get_wialon_geozones_report_template_id(request.user),
                item_id=unit_id,
                sess_id=sess_id,
            )

            try:
                r = exec_report(
                    request.user,
                    get_wialon_geozones_report_template_id(request.user),
                    dt_from,
                    dt_to,
                    object_id=unit_id,
                    sess_id=sess_id
                )
            except ReportException:
                raise APIProcessError(
                    'Не удалось получить отчет о поездках', code='wialon_geozones_report_error'
                )

            for table_index, table_info in enumerate(r['reportResult']['tables']):
                try:
                    pass
                    rows = get_report_rows(
                        request.user,
                        table_index,
                        table_info,
                        level=1,
                        sess_id=sess_id
                    )
                except ReportException:
                    raise APIProcessError(
                        'Не удалось извлечь данные о поездке', code='wialon_geozones_rows_error'
                    )

        return XMLResponse('ura/races.xml', context)


class URAMovingResource(URAResource):
    def post(self, request, *args, **kwargs):
        units = []

        context = self.get_context_data(**kwargs)
        context.update({
            'now': utcnow(),
            'units': units
        })

        units_els = request.data.xpath('/getMoving/unit')

        if not units_els:
            return error_response(
                'Не указаны объекты типа unit',
                code='units_not_found'
            )

        template_id = request.user.wialon_geozones_report_template_id
        if template_id is None:
            return error_response(
                'Не указан ID шаблона отчета по геозонам у текущего пользователя',
                code='geozones_report_not_found'
            )

        # for unit_el in units_els:
        #     pass

        return XMLResponse('ura/moving.xml', context)
