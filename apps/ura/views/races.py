# -*- coding: utf-8 -*-
import traceback
from collections import OrderedDict
import datetime

from base.exceptions import APIProcessError
from reports.utils import utc_to_local_time, parse_wialon_report_datetime
from snippets.utils.datetime import utcnow
from snippets.utils.email import send_trigger_email
from ura import models
from ura.lib.resources import URAResource
from ura.lib.response import error_response, XMLResponse
from ura.utils import parse_datetime, float_format
from ura.views.mixins import BaseUraRidesView


class URARacesResource(BaseUraRidesView, URAResource):
    model_mapping = {
        'date_begin': ('dateBegin', parse_datetime),
        'date_end': ('dateEnd', parse_datetime),
        'job_id': ('idJob', int),
        'unit_id': ('idUnit', int),
        'route_id': ('idRoute', int)
    }

    def __init__(self, **kwargs):
        super(URARacesResource, self).__init__(**kwargs)
        self.previous_point_name = None
        self.points_dict_by_name = {}
        self.route_endpoints = []

    def get_report_data_tables(self):
        self.report_data = {
            'unit_chronology': [],
            'unit_digital_sensors': [],
            'unit_engine_hours': [],
            'unit_trips': [],
            'unit_zones_visit': [],
        }

    def get_job(self):
        try:
            self.job = models.Job.objects.get(pk=self.input_data.get('job_id'))
        except models.Job.DoesNotExist:
            raise APIProcessError(
                'Задача c job_id=%s не найдена' % self.input_data['job_id'], code='job_not_found'
            )

        return self.job

    @staticmethod
    def prepare_output_data(job_info):
        # пост-фильтрация незаконченных маршрутов
        job_info['races'] = tuple(filter(
            lambda rc: len(
                tuple(filter(lambda p: p['type'] == 'endPoint', rc['points']))
            ) > 0,
            job_info['races']
        ))

        for race in job_info['races']:
            for point in race['points']:
                point['params']['moveTime'] = round(point['params']['moveTime'] / 60.0, 2)

    def make_races(self, races):
        # готовим точки маршрута от погрузки до разгрузки
        start_found = False
        self.route_endpoints = []

        for point in self.route_point_names:
            point_name = point.lower()

            if 'погрузка' in point_name:
                self.route_endpoints.append(point)
                start_found = True

            # разгрузкой заканчиваем маршрут
            if start_found and 'разгрузка' in point_name:
                self.route_endpoints.append(point)

        if len(self.route_endpoints) < 2:
            return

        current_point, points_iterator, new_loop = self.get_next_point()
        start_point, end_point = self.route_endpoints[0], self.route_endpoints[-1]
        race = {
            'date_start': None,
            'date_end': None,
            'points': []
        }

        last_distance = None

        start_found = False
        for row in self.ride_points:
            row_point_name = row['name']

            # если пробег открыт, добавляем
            if last_distance is not None:
                last_distance += row['params']['odoMeter']

            if row['name'] == 'SPACE':
                continue

            if row_point_name == current_point \
                    or (start_found and row_point_name in self.route_point_names):
                if row_point_name == start_point and start_found:
                    # фальстарт, машина вернулась в стартовую точку -
                    # значит начинаем рейс сначала
                    last_distance = None
                    race['points'] = []

                if row_point_name == current_point:
                    start_found = True

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

                if row_point_name == start_point:
                    # для стартовой точки открываем пробег
                    last_distance = row['params']['odoMeter']

                distance_delta = float_format(last_distance, -2)

                if row_point_name == start_point:
                    # для стартовой точки открываем пробег
                    if last_distance == .0:
                        last_distance += row['params']['odoMeter']
                    point_info['type'] = 'startPoint'
                    point_info['params']['fuelLevel'] = row['params']['startFuelLevel']

                    point_info['params']['distance'] = distance_delta

                elif row_point_name == end_point:
                    start_found = False
                    point_info['type'] = 'endPoint'
                    point_info['params']['fuelLevel'] = row['params']['endFuelLevel']
                    point_info['params']['distance'] = distance_delta

                else:
                    point_info['type'] = 'checkPoint'
                    point_info['params']['fuelLevelIn'] = row['params']['startFuelLevel']
                    point_info['params']['distanceIn'] = distance_delta

                # время движения получим из хронологии
                point_info['params']['moveTime'] = .0

                race['points'].append(point_info)

                # переключаем курсор поиска только для начального или конечного участка
                if row_point_name == current_point:
                    current_point, points_iterator, new_loop = self.get_next_point(
                        points_iterator
                    )

                if new_loop:
                    start_found = False
                    last_distance = None
                    if race['date_end'] is None:
                        race['date_end'] = row['time_out']

                    races.append(race)
                    race = {
                        'date_start': None,
                        'date_end': None,
                        'points': []
                    }
            self.previous_point_name = row_point_name

    def get_next_point(self, points_iterator=None):
        new_loop = False

        if points_iterator is None:
            points_iterator = iter(self.route_endpoints)

        try:
            current_point = next(points_iterator)
        except StopIteration:
            points_iterator = iter(self.route_endpoints)
            current_point = next(points_iterator)
            new_loop = True

        return current_point, points_iterator, new_loop

    def report_post_processing(self, job_info):
        for race in job_info['races']:
            race['date_start'] = utc_to_local_time(
                datetime.datetime.utcfromtimestamp(race['date_start']),
                self.request.user.ura_tz
            )
            race['date_end'] = utc_to_local_time(
                datetime.datetime.utcfromtimestamp(race['date_end']),
                self.request.user.ura_tz
            )

            for point in race['points']:
                point['time_in'] = utc_to_local_time(
                    datetime.datetime.utcfromtimestamp(point['time_in']),
                    self.request.user.ura_tz
                )
                point['time_out'] = utc_to_local_time(
                    datetime.datetime.utcfromtimestamp(point['time_out']),
                    self.request.user.ura_tz
                )

        for row in self.report_data['unit_chronology']:
            row_data = row['c']

            try:
                if row_data[0].lower() != 'поездка':
                    continue

            except AttributeError as e:
                send_trigger_email(
                    'Ошибка в работе интеграции Wialon', extra_data={
                        'Exception': str(e),
                        'Traceback': traceback.format_exc(),
                        'data': row_data,
                        'POST': self.request.body,
                        'user': self.request.user
                    }
                )

            time_from = utc_to_local_time(
                parse_wialon_report_datetime(
                    row_data[1]['t']
                    if isinstance(row_data[1], dict)
                    else row_data[1]
                ),
                self.request.user.ura_tz
            )

            time_until_value = row_data[2]['t'] \
                if isinstance(row_data[2], dict) else row_data[2]

            if 'unknown' in time_until_value.lower():
                time_until = self.input_data['date_end']
            else:
                time_until = utc_to_local_time(
                    parse_wialon_report_datetime(time_until_value),
                    self.request.user.ura_tz
                )

            for race in job_info['races']:
                for point in race['points']:
                    if point['time_in'] > time_until:
                        # дальнейшие строки точно не совпадут (виалон все сортирует по дате)
                        break

                    # если интервал точки меньше даты начала моточасов, значит еще не дошли
                    if point['time_out'] < time_from:
                        continue

                    delta = min(time_until, point['time_out']) - max(time_from, point['time_in'])
                    # не пересекаются:
                    if delta.total_seconds() < 0:
                        continue

                    point['params']['moveTime'] += delta.total_seconds()

    def post(self, request, **kwargs):
        jobs = []
        print('Start getRaces:\n' + str(request.body))

        context = self.get_context_data(**kwargs)
        context.update({
            'now': utcnow(),
            'jobs': jobs
        })

        jobs_els = request.data.xpath('/getRaces/job')

        if not jobs_els:
            return error_response('Не указаны объекты типа job', code='jobs_not_found')

        self.get_geozones_report_template_id()

        for job_el in jobs_els:
            self.get_input_data(job_el)
            self.unit_id = int(self.input_data.get('unit_id'))
            self.get_job()
            self.get_route()
            self.points_dict_by_name = {x['name']: x['id'] for x in self.route['points']}

            self.get_report_data()
            self.get_object_messages()
            self.start_timer()
            self.prepare_geozones_visits()

            self.ride_points = []
            self.process_messages()

            races = []
            job_info = {
                'obj': self.job,
                'races': races
            }

            self.make_races(races)

            self.report_post_processing(job_info)
            self.prepare_output_data(job_info)
            jobs.append(job_info)
            self.print_time_needed('Total calc')

        return XMLResponse('ura/races.xml', context)
