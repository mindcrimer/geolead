# -*- coding: utf-8 -*-
from collections import OrderedDict

from base.exceptions import ReportException
from base.utils import parse_float
from reports.utils import cleanup_and_request_report, get_period, \
    get_wialon_geozones_report_template_id, exec_report, get_report_rows, utc_to_local_time, \
    parse_wialon_report_datetime, parse_timedelta
from snippets.utils.datetime import utcnow
from ura import models
from ura.lib.resources import URAResource
from ura.lib.response import error_response, XMLResponse
from ura.utils import parse_datetime, parse_xml_input_data, float_format
from ura.wialon.api import get_routes_list, get_points_list
from ura.wialon.auth import authenticate_at_wialon
from ura.wialon.exceptions import WialonException


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
