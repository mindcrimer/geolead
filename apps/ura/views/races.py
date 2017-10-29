# -*- coding: utf-8 -*-
from collections import OrderedDict

from base.exceptions import ReportException
from reports.utils import cleanup_and_request_report, get_period, \
    get_wialon_geozones_report_template_id, exec_report, get_report_rows, utc_to_local_time, \
    parse_wialon_report_datetime
from snippets.utils.datetime import utcnow
from ura import models
from ura.lib.resources import URAResource
from ura.lib.response import error_response, XMLResponse
from ura.utils import parse_datetime, parse_xml_input_data, float_format
from ura.views.mixins import RidesMixin
from wialon.api import get_routes, get_points
from wialon.auth import authenticate_at_wialon
from wialon.exceptions import WialonException


class URARacesResource(RidesMixin, URAResource):
    model_mapping = {
        'date_begin': ('dateBegin', parse_datetime),
        'date_end': ('dateEnd', parse_datetime),
        'job_id': ('idJob', int),
        'unit_id': ('idUnit', int),
        'route_id': ('idRoute', int)
    }

    def __init__(self, **kwargs):
        super(URARacesResource, self).__init__(**kwargs)
        self.points_dict_by_name = {}

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

        self.sess_id = authenticate_at_wialon(request.user.wialon_token)
        routes_list = get_routes(sess_id=self.sess_id, with_points=True)
        routes_dict = {x['id']: x for x in routes_list}

        points_list = get_points(sess_id=self.sess_id)
        self.points_dict_by_name = {x['name']: x['id'] for x in points_list}

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

            self.route = routes_dict[route_id]
            points = routes_dict[route_id]['points']

            if len(points) < 2:
                return error_response(
                    'В маршруте %s менее 2 контрольных точек' % routes_dict[route_id]['name'],
                    code='route_no_points'
                )

            dt_from, dt_to = get_period(
                data['date_begin'],
                data['date_end']
            )

            cleanup_and_request_report(
                request.user,
                get_wialon_geozones_report_template_id(request.user),
                item_id=unit_id,
                sess_id=self.sess_id,
            )

            try:
                r = exec_report(
                    request.user,
                    get_wialon_geozones_report_template_id(request.user),
                    dt_from,
                    dt_to,
                    object_id=unit_id,
                    sess_id=self.sess_id
                )
            except ReportException:
                raise WialonException('Не удалось получить отчет о поездках')

            report_data = {
                'unit_trips': [],
                'unit_chronology': []
            }

            for table_index, table_info in enumerate(r['reportResult']['tables']):
                if table_info['name'] not in report_data:
                    continue

                try:
                    rows = get_report_rows(
                        request.user,
                        table_index,
                        table_info['rows'],
                        level=1,
                        sess_id=self.sess_id
                    )

                    report_data[table_info['name']] = rows

                except ReportException:
                    raise WialonException('Не удалось извлечь данные о поездке')

            self.normalize_rides(
                report_data, utc_to_local_time(data.get('date_end'), request.user.ura_tz)
            )

            self.all_points_names = set()
            self.all_points = {}
            self.route_point_names = [x['name'] for x in self.route['points']]

            for r in routes_dict.values():
                self.all_points_names.update([x['name'] for x in r['points']])
                self.all_points.update({x['id']: x for x in r['points']})

            self.make_races(points, races)

            if not races:
                self.previous_point_name = None
                self.make_races(list(reversed(points)), races)

            for row in report_data['unit_chronology']:
                row_data = row['c']

                if row_data[0].lower() == 'parking':
                    continue

                time_from = utc_to_local_time(
                    parse_wialon_report_datetime(
                        row_data[1]['t']
                        if isinstance(row_data[1], dict)
                        else row_data[1]
                    ),
                    request.user.ura_tz
                )
                time_until = utc_to_local_time(
                    parse_wialon_report_datetime(
                        row_data[2]['t']
                        if isinstance(row_data[2], dict)
                        else row_data[2]
                    ),
                    request.user.ura_tz
                )

                for race in job_info['races']:
                    for point in race['points']:
                        if point['time_in'] > time_until:
                            # дальнейшие строки точно не совпадут (виалон все сортирует по дате)
                            break

                        # если интервал точки меньше даты начала моточасов, значит еще не дошли
                        if point['time_out'] < time_from:
                            continue

                        delta = min(time_until, point['time_out']) \
                            - max(time_from, point['time_in'])
                        # не пересекаются:
                        if delta.seconds < 0 or delta.days < 0:
                            continue

                        point['params']['moveTime'] += delta.seconds

            for race in job_info['races']:
                for point in race['points']:
                    point['params']['moveTime'] = round(point['params']['moveTime'] / 60.0, 2)

            # пост-фильтрация незаконченных маршрутов
            job_info['races'] = filter(
                lambda rc: len(
                    tuple(filter(lambda p: p['type'] == 'endPoint', rc['points']))
                ) > 0,
                job_info['races']
            )
            jobs.append(job_info)

        return XMLResponse('ura/races.xml', context)

    def make_races(self, points, races):
        current_point, points_iterator, new_loop = self.get_next_point(points)
        start_point, end_point = points[0], points[-1]
        race = {
            'date_start': None,
            'date_end': None,
            'points': []
        }

        last_distance = .0

        for row in self.normalized_rides:
            row_point_name = self.get_normalized_point_name(row)

            if row_point_name == current_point['name']:
                if race['date_start'] is None:
                    race['date_start'] = row['time_in']

                point_id = self.points_dict_by_name.get(row_point_name, 'NOT_FOUND')

                point_info = {
                    'name': row_point_name,
                    'time_in': row['time_in'],
                    'time_out': row['time_out'],
                    'id': point_id,
                    'params': OrderedDict()
                }

                last_distance += row['distance']
                distance_delta = float_format(last_distance, -2)

                if row_point_name == start_point['name']:
                    point_info['type'] = 'startPoint'
                    point_info['params']['fuelLevel'] = row['fuel_start']

                    point_info['params']['distance'] = distance_delta

                elif row_point_name == end_point['name']:
                    point_info['type'] = 'endPoint'
                    point_info['params']['fuelLevel'] = row['fuel_end']
                    point_info['params']['distance'] = distance_delta

                else:
                    point_info['type'] = 'checkPoint'
                    point_info['params']['fuelLevelIn'] = row['fuel_start']
                    point_info['params']['distanceIn'] = distance_delta

                # время движения получим из хронологии
                point_info['params']['moveTime'] = .0

                race['points'].append(point_info)

                current_point, points_iterator, new_loop = self.get_next_point(
                    points, points_iterator
                )

                if new_loop:
                    last_distance = .0
                    if race['date_end'] is None:
                        race['date_end'] = row['time_out']

                    races.append(race)
                    race = {
                        'date_start': None,
                        'date_end': None,
                        'points': []
                    }
            self.previous_point_name = row_point_name
