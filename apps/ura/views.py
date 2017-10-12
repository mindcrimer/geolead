# -*- coding: utf-8 -*-
from collections import OrderedDict
from copy import deepcopy
import datetime

from django.db.models import Q

from base.utils import parse_float
from base.exceptions import APIProcessError, ReportException
from reports.utils import get_period, get_wialon_geozones_report_template_id, \
    cleanup_and_request_report, exec_report, get_report_rows, parse_wialon_report_datetime, \
    parse_timedelta, utc_to_local_time
from snippets.utils.datetime import utcnow
from ura import models
from ura.lib.resources import URAResource
from ura.lib.response import XMLResponse, error_response
from ura.utils import parse_datetime, get_organization_user, parse_xml_input_data, float_format
from ura.wialon.api import get_drivers_list, get_routes_list, get_units_list, get_points_list
from ura.wialon.auth import authenticate_at_wialon
from ura.wialon.exceptions import WialonException
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
            return error_response(str(e), code=e.code)

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


class URAPointsResource(URAResource):
    """Список геозон (точек)"""
    def post(self, request, *args, **kwargs):

        doc = request.data.xpath('/pointsRequest')
        if len(doc) < 1:
            return error_response(
                'Не найден объект pointsRequest', code='pointsRequest_not_found'
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
            points = get_points_list(user)
        except APIProcessError as e:
            return error_response(str(e), code=e.code)

        context = self.get_context_data(**kwargs)
        context.update({
            'doc_id': doc_id,
            'create_date': utcnow(),
            'points': points,
            'org_id': org_id
        })

        return XMLResponse('ura/points.xml', context)


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
            return error_response(str(e), code=e.code)

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
            return error_response(str(e), code=e.code)

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
#             return error_response(str(e), code=e.code)
#
#         try:
#             routes = get_routes_list(request.user)
#         except APIProcessError as e:
#             return error_response(str(e), code=e.code)
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

                name = data.get('name')
                if not name:
                    return error_response('Не указан параметр jobName', code='jobName_not_found')

                job = self.model.objects.create(**data)
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
        'job_id': ('idJob', int),
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

                job_id = data.pop('job_id')
                if not job_id:
                    return error_response('Не указан параметр idJob', code='idJob_not_found')

                if data['date_end'] <= data['date_begin']:
                    self.model.objects.filter(id=job_id).delete()
                else:
                    try:
                        job = self.model.objects.get(id=job_id)
                    except self.model.DoesNotExist:
                        return error_response(
                            'Задание с ID=%s не найдено' % job_id, code='job_not_found'
                        )

                    for k, v in data.iems():
                        setattr(job, k, v)
                        job.save()
                    jobs.append(job)

        context = self.get_context_data(**kwargs)
        context.update({
            'now': utcnow(),
            'breakJobs': jobs
        })

        return XMLResponse('ura/ackBreakJobs.xml', context)


RIDES_GEOZONE_FROM_COL = 1
RIDES_DATE_FROM_COL = 3
RIDES_DATE_TO_COL = 4
RIDES_DISTANCE_END_COL = 5
RIDES_TIME_TOTAL_COL = 6
RIDES_TIME_PARKING_COL = 7
RIDES_FUEL_LEVEL_START_COL = 8
RIDES_FUEL_LEVEL_END_COL = 9
RIDES_ODOMETER_START_COL = 10
RIDES_ODOMETER_END_COL = 11


class URARacesResource(URAResource):
    model_mapping = {
        'date_begin': ('dateBegin', parse_datetime),
        'date_end': ('dateEnd', parse_datetime),
        'job_id': ('idJob', int),
        'unit_id': ('idUnit', int),
        'route_id': ('idRoute', int)
    }

    @staticmethod
    def get_next_point(points, points_iterator=None):
        new_loop = False

        if points_iterator is None:
            points_iterator = iter(points)

        try:
            current_point = next(points_iterator)
        except StopIteration:
            points_iterator = iter(points)
            current_point = next(points_iterator)
            new_loop = True

        return current_point, points_iterator, new_loop

    def post(self, request, *args, **kwargs):
        jobs = []

        context = self.get_context_data(**kwargs)
        context.update({
            'now': utcnow(),
            'jobs': jobs
        })

        sess_id = authenticate_at_wialon(request.user.wialon_token)
        routes_list = get_routes_list(sess_id=sess_id, get_points=True)
        routes_dict = {x['id']: x for x in routes_list}

        points_list = get_points_list(sess_id=sess_id)
        points_dict_by_name = {x['name']: x['id'] for x in points_list}

        jobs_els = request.data.xpath('/getRaces/job')

        if not jobs_els:
            return error_response('Не указаны объекты типа job', code='jobs_not_found')

        for j in jobs_els:
            data = parse_xml_input_data(request, self.model_mapping, j)

            try:
                job = data['job'] = models.UraJob.objects.get(pk=data['job_id'])
            except models.UraJob.DoesNotExist:
                return error_response(
                    'Задача c ID=%s не найдена' % data['job_id'], code='job_not_found'
                )

            races = []
            job_info = {
                'obj': job,
                'races': races
            }

            unit_id = int(data.get('unit_id', job.unit_id))
            route_id = int(data.get('route_id', job.route_id))
            if route_id not in routes_dict:
                return error_response(
                    'Маршрут с ID=%s не найден' % route_id, code='routes_not_found'
                )

            dt_from, dt_to = get_period(
                data['date_begin'],
                data['date_end']
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
                raise WialonException('Не удалось получить отчет о поездках')

            report_data = {
                'unit_fillings': [],
                'unit_engine_hours': [],
                'unit_rides': [],
                'unit_thefts': []
            }
            for table_index, table_info in enumerate(r['reportResult']['tables']):
                try:
                    rows = get_report_rows(
                        request.user,
                        table_index,
                        table_info,
                        level=1,
                        sess_id=sess_id
                    )

                    report_data[table_info['name']] = rows

                except ReportException:
                    raise WialonException('Не удалось извлечь данные о поездке')

            points = routes_dict[route_id]['points']
            if len(points) < 2:
                return error_response(
                    'В маршруте %s менее 2 контрольных точек' % routes_dict[route_id]['name'],
                    code='route_no_points'
                )

            current_point, points_iterator, new_loop = self.get_next_point(points)
            start_point, end_point = points[0], points[-1]
            race = {
                'date_start': None,
                'date_end': None,
                'points': []
            }

            last_distance = .0

            for row in report_data['unit_rides']:
                row_data = row['c']
                row_point_name = row_data[RIDES_GEOZONE_FROM_COL].strip()

                if row_point_name == current_point:
                    time_in = row_data[RIDES_DATE_FROM_COL]['t'] \
                        if isinstance(row_data[RIDES_DATE_FROM_COL],  dict) \
                        else row_data[RIDES_DATE_FROM_COL]

                    time_in = utc_to_local_time(
                        parse_wialon_report_datetime(time_in),
                        request.user.ura_tz
                    )

                    time_out = row_data[RIDES_DATE_TO_COL]['t'] \
                        if isinstance(row_data[RIDES_DATE_TO_COL], dict) \
                        else row_data[RIDES_DATE_TO_COL]

                    time_out = utc_to_local_time(
                        parse_wialon_report_datetime(time_out),
                        request.user.ura_tz
                    )

                    if race['date_start'] is None:
                        race['date_start'] = time_in

                    point_id = points_dict_by_name.get(row_point_name, 'NOT_FOUND')

                    point_info = {
                        'time_in': time_in,
                        'time_out': time_out,
                        'id': point_id,
                        'params': OrderedDict()
                    }

                    current_distance = parse_float(
                        row_data[RIDES_DISTANCE_END_COL]
                    )

                    last_distance += current_distance
                    distance_delta = float_format(last_distance, -2)

                    if row_point_name == start_point:
                        point_info['type'] = 'startPoint'
                        point_info['params']['fuelLevel'] = parse_float(
                            row_data[RIDES_FUEL_LEVEL_START_COL]
                        )

                        point_info['params']['distance'] = distance_delta

                    elif row_point_name == end_point:
                        point_info['type'] = 'endPoint'
                        point_info['params']['fuelLevel'] = parse_float(
                            row_data[RIDES_FUEL_LEVEL_END_COL]
                        )
                        point_info['params']['distance'] = distance_delta

                    else:
                        point_info['type'] = 'checkPoint'
                        point_info['params']['fuelLevelIn'] = parse_float(
                            row_data[RIDES_FUEL_LEVEL_START_COL]
                        )
                        point_info['params']['distanceIn'] = distance_delta

                        time_total = parse_timedelta(row_data[RIDES_TIME_TOTAL_COL]).seconds
                        time_parking = parse_timedelta(row_data[RIDES_TIME_PARKING_COL]).seconds
                        point_info['params']['moveTime'] = max(0, time_total - time_parking)

                    race['points'].append(point_info)

                    current_point, points_iterator, new_loop = self.get_next_point(
                        points, points_iterator
                    )

                    if new_loop:
                        last_distance = .0
                        if race['date_end'] is None:
                            race['date_end'] = time_out

                        races.append(race)
                        race = {
                            'date_start': None,
                            'date_end': None,
                            'points': []
                        }

            # пост-фильтрация незаконченных маршрутов
            job_info['races'] = filter(
                lambda rc: len(
                    tuple(filter(lambda p: p['type'] == 'endPoint', rc['points']))
                ) > 0,
                job_info['races']
            )
            jobs.append(job_info)

        return XMLResponse('ura/races.xml', context)


class URAMovingResource(URAResource):
    model_mapping = {
        'date_begin': ('dateBegin', parse_datetime),
        'date_end': ('dateEnd', parse_datetime),
        'unit_id': ('idUnit', int),
    }

    def post(self, request, *args, **kwargs):
        units = []

        context = self.get_context_data(**kwargs)
        context.update({
            'now': utcnow(),
            'units': units
        })

        sess_id = authenticate_at_wialon(request.user.wialon_token)
        routes_list = get_routes_list(sess_id=sess_id, get_points=True)
        routes_dict = {x['id']: x for x in routes_list}

        units_els = request.data.xpath('/getMoving/unit')

        if not units_els:
            return error_response(
                'Не указаны объекты типа unit', code='units_not_found'
            )

        template_id = request.user.wialon_geozones_report_template_id
        if template_id is None:
            return error_response(
                'Не указан ID шаблона отчета по геозонам у текущего пользователя',
                code='geozones_report_not_found'
            )

        for unit_el in units_els:
            data = parse_xml_input_data(request, self.model_mapping, unit_el)

            unit_id = int(data.get('unit_id', data['unit_id']))

            job = models.UraJob.objects.filter(
                unit_id=unit_id,
                date_begin__gte=data.get('date_begin'),
                date_end__lte=data.get('date_end')
            ).first()

            route = None
            if job:
                try:
                    route = routes_dict.get(int(job.route_id))
                except ValueError:
                    pass

            unit_info = {
                'id': unit_id,
                'date_begin': utc_to_local_time(data.get('date_begin'), request.user.ura_tz),
                'date_end': utc_to_local_time(data.get('date_end'), request.user.ura_tz),
                'points': []
            }

            dt_from, dt_to = get_period(
                data['date_begin'],
                data['date_end'],
            )

            cleanup_and_request_report(
                request.user,
                get_wialon_geozones_report_template_id(request.user),
                item_id=unit_id,
                sess_id=sess_id
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
                raise WialonException('Не удалось получить отчет о поездках')

            report_data = {
                'unit_fillings': [],
                'unit_engine_hours': [],
                'unit_rides': [],
                'unit_thefts': []
            }

            for table_index, table_info in enumerate(r['reportResult']['tables']):
                try:
                    rows = get_report_rows(
                        request.user,
                        table_index,
                        table_info,
                        level=1,
                        sess_id=sess_id
                    )

                    report_data[table_info['name']] = rows

                except ReportException:
                    raise WialonException('Не удалось извлечь данные о поездке')

            for row in report_data['unit_rides']:
                row_data = row['c']

                time_in = row_data[RIDES_DATE_FROM_COL]['t'] \
                    if isinstance(row_data[RIDES_DATE_FROM_COL], dict) \
                    else row_data[RIDES_DATE_FROM_COL]

                time_in = utc_to_local_time(
                    parse_wialon_report_datetime(time_in),
                    request.user.ura_tz
                )

                time_out = row_data[RIDES_DATE_TO_COL]['t'] \
                    if isinstance(row_data[RIDES_DATE_TO_COL], dict) \
                    else row_data[RIDES_DATE_TO_COL]

                time_out = utc_to_local_time(
                    parse_wialon_report_datetime(time_out),
                    request.user.ura_tz
                )

                time_total = parse_timedelta(row_data[RIDES_TIME_TOTAL_COL]).seconds
                time_parking = parse_timedelta(row_data[RIDES_TIME_PARKING_COL]).seconds
                move_time = time_total - time_parking

                point_name = row_data[RIDES_GEOZONE_FROM_COL]
                if not route or point_name not in route['points']:
                    point_name = 'SPACE'

                point_info = {
                    'name': point_name,
                    'time_in': time_in,
                    'time_out': time_out,
                    'params': OrderedDict((
                        ('startFuelLevel', parse_float(row_data[RIDES_FUEL_LEVEL_START_COL])),
                        ('endFuelLevel', parse_float(row_data[RIDES_FUEL_LEVEL_END_COL])),
                        ('fuelRefill', .0),
                        ('fuelDrain', .0),
                        ('stopMinutes', max(0, time_parking)),
                        ('moveMinutes', max(0, move_time)),
                        ('motoHours', 0),
                        (
                            'odoMeter',
                            float_format(parse_float(row_data[RIDES_DISTANCE_END_COL]), -2)
                        )
                    ))
                }

                try:
                    previous_point = unit_info['points'][-1]
                    # добавляем еще запись SPACE,
                    # если машина была более 30 секунд непонятно где
                    if point_info['time_in'] - previous_point['time_out']\
                            >= datetime.timedelta(seconds=30):

                        # если предыдущая точка SPACE, удлиняем выход из нее до текущего входа
                        if previous_point['name'] == 'SPACE':
                            previous_point['time_out'] = point_info['time_in']

                        # если же текущая точка SPACE, удлиняем вход в нее
                        # до выхода из предыдущей известной точки
                        elif point_info['name'] == 'SPACE':
                            point_info['time_in'] = previous_point['time_out']
                        # если предыщуая и текущая точки не SPACE, создаем новый интервал,
                        # скопированный из текущего, где время входа - это время выхода из
                        # предыдущей точки, а время выхода - это время входа в текущую
                        else:
                            extra_space_point = deepcopy(point_info)
                            extra_space_point.update(
                                name='SPACE',
                                time_in=previous_point['time_out'],
                                time_out=point_info['time_in']
                            )

                            # но не копируем время движения и стоянки, так как они неизвестны
                            extra_space_point['params'].update(
                                stopMinutes=0,
                                moveMinute=0
                            )

                            unit_info['points'].append(extra_space_point)

                except IndexError:
                    pass

                # склеиваем подряд идущие SPACE
                if point_name == 'SPACE':
                    try:
                        previous_point = unit_info['points'][-1]
                        if previous_point['name'] == 'SPACE':
                            # обновляем в предыдущей точке те метрики, которые есть в текущей:
                            previous_point['time_out'] = point_info['time_out']
                            previous_point['params']['endFuelLevel'] = \
                                point_info['params']['endFuelLevel']
                            previous_point['params']['stopMinutes'] += \
                                point_info['params']['stopMinutes']
                            previous_point['params']['moveMinutes'] += \
                                point_info['params']['moveMinutes']
                            previous_point['params']['odoMeter'] = point_info['params']['odoMeter']
                            # сливы, заправки и моточасы не обновляем, они тянутся ниже
                            continue
                    except IndexError:
                        pass

                unit_info['points'].append(point_info)

            for row in report_data['unit_thefts']:
                volume = parse_float(row['c'][2])

                if volume > .0 and row['c'][1]:
                    dt = utc_to_local_time(
                        parse_wialon_report_datetime(
                            row['c'][1]['t']
                            if isinstance(row['c'][1], dict)
                            else row['c'][1]
                        ),
                        request.user.ura_tz
                    )

                    for point in unit_info['points']:
                        if point['time_in'] <= dt <= point['time_out']:
                            point['params']['fuelDrain'] += volume
                            break

            for row in report_data['unit_fillings']:
                volume = parse_float(row['c'][1])

                if volume > .0:
                    dt = utc_to_local_time(
                        parse_wialon_report_datetime(
                            row['c'][0]['t']
                            if isinstance(row['c'][0], dict)
                            else row['c'][0]
                        ),
                        request.user.ura_tz
                    )

                    for point in unit_info['points']:
                        if point['time_in'] <= dt <= point['time_out']:
                            point['params']['fuelRefill'] += volume
                            break

            # рассчитываем моточасы пропорционально интервалам
            for row in report_data['unit_engine_hours']:
                time_from = utc_to_local_time(
                    parse_wialon_report_datetime(
                        row['c'][0]['t']
                        if isinstance(row['c'][0], dict)
                        else row['c'][0]
                    ),
                    request.user.ura_tz
                )
                time_until = utc_to_local_time(
                    parse_wialon_report_datetime(
                        row['c'][1]['t']
                        if isinstance(row['c'][1], dict)
                        else row['c'][1]
                    ),
                    request.user.ura_tz
                )

                for point in unit_info['points']:
                    if point['time_in'] > time_until:
                        # дальнейшие строки точно не совпадут (виалон все сортирует по дате)
                        break

                    # если интервал точки меньше даты начала моточасов, значит еще не дошли
                    if point['time_out'] < time_from:
                        continue

                    delta = min(time_until, point['time_out']) - max(time_from, point['time_in'])
                    # не пересекаются:
                    if delta.seconds < 0 or delta.days < 0:
                        continue

                    point['params']['motoHours'] += delta.seconds

            # проверяем сходимость данных для SPACE точек
            for i, point in enumerate(unit_info['points']):
                if point['name'] == 'SPACE':
                    previous_point, next_point = None, None
                    if i > 0:
                        try:
                            previous_point = unit_info['points'][i-1]
                        except IndexError:
                            pass

                    try:
                        next_point = unit_info['points'][i+1]
                    except IndexError:
                        pass

                    if previous_point:
                        point['params']['startFuelLevel'] = \
                            previous_point['params']['endFuelLevel']

                    if next_point:
                        point['params']['endFuelLevel'] = \
                            next_point['params']['startFuelLevel']

                    point['params']['moveMinutes'] = (
                        point['time_out'] - point['time_in']
                    ).seconds - point['params']['stopMinutes']

                point['params']['moveMinutes'] = round(point['params']['moveMinutes'] / 60.0, 2)
                point['params']['stopMinutes'] = round(point['params']['stopMinutes'] / 60.0, 2)
                point['params']['motoHours'] = round(point['params']['motoHours'] / 3600.0, 2)

            units.append(unit_info)

        return XMLResponse('ura/moving.xml', context)
