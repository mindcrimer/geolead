# -*- coding: utf-8 -*-
import datetime
from collections import OrderedDict

from base.exceptions import APIProcessError
from base.utils import parse_float, get_distance
from reports.utils import utc_to_local_time, parse_wialon_report_datetime
from snippets.utils.datetime import utcnow
from ura import models
from ura.lib.response import XMLResponse, error_response
from ura.views.mixins import BaseUraRidesView


class URAMovingResource(BaseUraRidesView):
    """getMoving - движение машины"""
    def get_report_data_tables(self):
        self.report_data = {
            'unit_fillings': [],
            'unit_thefts': [],
            'unit_engine_hours': [],
            'unit_zones_visit': [],
            'unit_chronology': []
        }

    def report_post_processing(self, unit_info):
        for point in unit_info['points']:
            point['time_in'] = utc_to_local_time(
                datetime.datetime.utcfromtimestamp(point['time_in']),
                self.request.user.ura_tz
            )
            point['time_out'] = utc_to_local_time(
                datetime.datetime.utcfromtimestamp(point['time_out']),
                self.request.user.ura_tz
            )

        self.print_time_needed('points utc_to_local')

        for row in self.report_data['unit_thefts']:
            volume = parse_float(row['c'][2])

            if volume > .0 and row['c'][1]:
                dt = utc_to_local_time(
                    parse_wialon_report_datetime(
                        row['c'][1]['t']
                        if isinstance(row['c'][1], dict)
                        else row['c'][1]
                    ),
                    self.request.user.ura_tz
                )

                for point in unit_info['points']:
                    if point['time_in'] <= dt <= point['time_out']:
                        point['params']['fuelDrain'] += volume
                        break

        self.print_time_needed('fuelDrain')

        for row in self.report_data['unit_fillings']:
            volume = parse_float(row['c'][1])

            if volume > .0:
                dt = utc_to_local_time(
                    parse_wialon_report_datetime(
                        row['c'][0]['t']
                        if isinstance(row['c'][0], dict)
                        else row['c'][0]
                    ),
                    self.request.user.ura_tz
                )

                for point in unit_info['points']:
                    if point['time_in'] <= dt <= point['time_out']:
                        point['params']['fuelRefill'] += volume
                        break

        self.print_time_needed('fuelRefill')

        # рассчитываем моточасы пропорционально интервалам
        for row in self.report_data['unit_engine_hours']:
            time_from = utc_to_local_time(
                parse_wialon_report_datetime(
                    row['c'][0]['t']
                    if isinstance(row['c'][0], dict)
                    else row['c'][0]
                ),
                self.request.user.ura_tz
            )

            time_until_value = row['c'][1]['t'] \
                if isinstance(row['c'][1], dict) else row['c'][1]

            if 'unknown' in time_until_value.lower():
                time_until = utc_to_local_time(
                    self.input_data['date_end'], self.request.user.ura_tz
                )
            else:
                time_until = utc_to_local_time(
                    parse_wialon_report_datetime(time_until_value),
                    self.request.user.ura_tz
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

        self.print_time_needed('motoHours')

        for row in self.report_data['unit_chronology']:
            row_data = row['c']
            if row_data[0].lower() not in ('parking', 'стоянка', 'остановка'):
                continue

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

            for point in unit_info['points']:
                if point['time_in'] > time_until:
                    # дальнейшие строки точно не совпадут (виалон все сортирует по дате)
                    break

                # если интервал точки меньше даты начала хронологии, значит еще не дошли
                if point['time_out'] < time_from:
                    continue

                delta = min(time_until, point['time_out']) - max(time_from, point['time_in'])
                # не пересекаются:
                if delta.seconds < 0 or delta.days < 0:
                    continue

                point['params']['stopMinutes'] += delta.seconds

        self.print_time_needed('MoveTime')

    @staticmethod
    def prepare_output_data(unit_info):
        # преобразуем секунды в минуты и часы
        for i, point in enumerate(unit_info['points']):
            point['params']['moveMinutes'] = round(
                (
                    (point['time_out'] - point['time_in']).seconds
                    - point['params']['stopMinutes']
                ) / 60.0, 2
            )
            point['params']['stopMinutes'] = round(
                point['params']['stopMinutes'] / 60.0, 2
            )
            point['params']['motoHours'] = round(
                point['params']['motoHours'] / 3600.0, 2
            )
            point['params']['odoMeter'] = round(point['params']['odoMeter'], 2)

    def process_messages(self, unit_info):
        prev_message = None
        current_geozone = None
        messages_length0 = len(self.messages) - 1

        self.print_time_needed('Prepare')

        for i, message in enumerate(self.messages):
            message['distance'] = .0

            if prev_message:
                # получаем пройденное расстояние для предыдущей точки
                # TODO: попробовать через geopy
                prev_message['distance'] = get_distance(
                    prev_message['pos']['x'],
                    prev_message['pos']['y'],
                    message['pos']['x'],
                    message['pos']['y']
                )

            # находим по времени в сообщении наличие на момент времени в геозоне
            found_geozone = False
            for geozone in self.unit_zones_visit:

                # если точка входит по времени в геозону
                if geozone['time_in'] <= message['t'] <= geozone['time_out']:

                    # и текущая геозона сменилась - закрываем предыдущую, открывая новую
                    if not current_geozone or geozone['name'] != current_geozone['name']:
                        self.add_new_point(message, prev_message, geozone, unit_info)
                        current_geozone = geozone

                    found_geozone = True
                    break

            if prev_message:
                self.current_distance += prev_message['distance']

            if not found_geozone:
                if unit_info['points'] \
                        and unit_info['points'][-1]['name'] == 'SPACE':
                    unit_info['points'][-1]['time_out'] = message['t']
                    unit_info['points'][-1]['params']['odoMeter'] = self.current_distance
                else:
                    self.add_new_point(message, prev_message, {
                        'name': 'SPACE',
                        'time_in': message['t'],
                        'time_out': message['t']
                    }, unit_info)

            # если сообщение последнее, то закрываем пробег последнего участка
            if i == messages_length0:
                fuel_level = round(self.get_fuel_level(message), 2)
                unit_info['points'][-1]['params']['endFuelLevel'] = fuel_level
                unit_info['points'][-1]['params']['odoMeter'] = \
                    self.current_distance
            prev_message = message

        self.print_time_needed('Points build')

    def add_new_point(self, message, prev_message, geozone, unit_info):
        fuel_level = round(self.get_fuel_level(message), 2)

        new_point = {
            'name': geozone['name'],
            'time_in': geozone['time_in'],
            'time_out': geozone['time_out'],
            'params': OrderedDict((
                ('startFuelLevel', fuel_level),
                ('endFuelLevel', .0),
                ('fuelRefill', .0),
                ('fuelDrain', .0),
                ('stopMinutes', .0),
                ('moveMinutes', .0),
                ('motoHours', .0),
                ('odoMeter', .0)
            ))
        }

        # закрываем пробег и топливо на конец участка для предыдущей точки
        if prev_message:
            fuel_level = round(self.get_fuel_level(prev_message), 2)
        else:
            fuel_level = .0

        try:
            previous_geozone = unit_info['points'][-1]
            previous_geozone['time_out'] = geozone['time_in']
            previous_geozone['params']['odoMeter'] = self.current_distance
            previous_geozone['params']['endFuelLevel'] = fuel_level
        except IndexError:
            pass

        # сбрасываем пробег
        self.current_distance = .0

        unit_info['points'].append(new_point)

    def get_job(self):
        self.job = models.UraJob.objects.filter(
            date_begin__gte=self.input_data.get('date_begin'),
            date_end__lte=self.input_data.get('date_end'),
            unit_id=self.unit_id
        ).first()

        if not self.job:
            raise APIProcessError(
                'Задача c unit_id=%s не найдена' % self.input_data['job_id'], code='job_not_found'
            )

        return self.job

    def post(self, request, **kwargs):
        units = []

        context = self.get_context_data(**kwargs)
        context.update({
            'now': utcnow(),
            'units': units
        })

        units_els = request.data.xpath('/getMoving/unit')
        if not units_els:
            return error_response(
                'Не указаны объекты типа unit', code='units_not_found'
            )

        self.get_geozones_report_template_id()

        for unit_el in units_els:
            self.get_input_data(unit_el)
            self.unit_id = int(self.input_data.get('unit_id'))
            self.get_job()
            self.get_route()
            self.get_report_data()
            self.get_object_settings()
            self.get_object_messages()

            unit_info = {
                'id': self.unit_id,
                'date_begin': utc_to_local_time(
                    self.input_data['date_begin'], request.user.ura_tz
                ),
                'date_end': utc_to_local_time(self.input_data['date_end'], request.user.ura_tz),
                'points': []
            }

            self.start_timer()
            self.prepare_geozones_visits()
            self.process_messages(unit_info)
            self.report_post_processing(unit_info)
            self.prepare_output_data(unit_info)

            units.append(unit_info)
            self.print_time_needed('Total calc')

        return XMLResponse('ura/moving.xml', context)
