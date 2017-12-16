# -*- coding: utf-8 -*-
from collections import OrderedDict
from copy import deepcopy
import datetime

from base.exceptions import ReportException
from base.utils import parse_float
from reports.utils import parse_wialon_report_datetime, utc_to_local_time, get_period, \
    cleanup_and_request_report, exec_report, get_report_rows, get_wialon_report_template_id
from snippets.utils.datetime import utcnow
from ura import models
from ura.lib.resources import URAResource
from ura.lib.response import XMLResponse, error_response
from ura.utils import parse_datetime, parse_xml_input_data
from ura.views.old.mixins import RidesMixin
from wialon.api import get_routes
from wialon.auth import get_wialon_session_key
from wialon.exceptions import WialonException


class URAMovingResource(RidesMixin, URAResource):
    model_mapping = {
        'date_begin': ('dateBegin', parse_datetime),
        'date_end': ('dateEnd', parse_datetime),
        'unit_id': ('idUnit', int),
    }

    def get_geozones_report_template_id(self):
        report_template_id = get_wialon_report_template_id('geozones', self.request.user)
        if report_template_id is None:
            return error_response(
                'Не указан ID шаблона отчета по геозонам у текущего пользователя',
                code='geozones_report_not_found'
            )
        return report_template_id

    def post(self, request, *args, **kwargs):
        units = []

        context = self.get_context_data(**kwargs)
        context.update({
            'now': utcnow(),
            'units': units
        })

        self.sess_id = get_wialon_session_key(request.user)
        routes_list = get_routes(sess_id=self.sess_id, with_points=True)
        routes_dict = {x['id']: x for x in routes_list}

        units_els = request.data.xpath('/getMoving/unit')

        if not units_els:
            return error_response(
                'Не указаны объекты типа unit', code='units_not_found'
            )

        template_id = self.get_geozones_report_template_id()
        if template_id is None:
            return error_response(
                'Не указан ID шаблона отчета по геозонам у текущего пользователя',
                code='geozones_report_not_found'
            )

        template_id = get_wialon_report_template_id('geozones', request.user)
        for unit_el in units_els:
            data = parse_xml_input_data(request, self.model_mapping, unit_el)

            unit_id = int(data.get('unit_id', data['unit_id']))

            job = models.UraJob.objects.filter(
                unit_id=unit_id,
                date_begin__gte=data.get('date_begin'),
                date_end__lte=data.get('date_end')
            ).first()

            if job:
                try:
                    self.route = routes_dict.get(int(job.route_id))
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
                data['date_end']
            )

            cleanup_and_request_report(
                request.user, template_id, item_id=unit_id, sess_id=self.sess_id
            )

            try:
                r = exec_report(
                    request.user, template_id, dt_from, dt_to, object_id=unit_id,
                    sess_id=self.sess_id
                )
            except ReportException:
                raise WialonException('Не удалось получить в Wialon отчет о поездках')

            report_data = {
                'unit_fillings': [],
                'unit_thefts': [],
                'unit_engine_hours': [],
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
                    raise WialonException('Не удалось получить в Wialon отчет о поездках')

            self.normalize_rides(report_data, unit_info['date_end'])

            self.all_points_names = set()
            self.all_points = {}
            self.route_point_names = [x['name'] for x in self.route['points']] \
                if self.route else []

            for r in routes_dict.values():
                self.all_points_names.update([x['name'] for x in r['points']])
                self.all_points.update({x['id']: x for x in r['points']})

            for row in self.normalized_rides:
                point_name = self.get_normalized_point_name(row)

                point_info = {
                    'name': point_name,
                    'time_in': row['time_in'],
                    'time_out': row['time_out'],
                    'params': OrderedDict((
                        ('startFuelLevel', row['fuel_start']),
                        ('endFuelLevel', row['fuel_end']),
                        ('fuelRefill', .0),
                        ('fuelDrain', .0),
                        ('stopMinutes', .0),
                        ('moveMinutes', .0),
                        ('motoHours', 0),
                        ('odoMeter', row['distance'])
                    ))
                }

                # вряд ли сработает, но на всякий случай проверяем на "выпадения"
                # из маршрута по времени
                try:
                    previous_point = unit_info['points'][-1]
                    # добавляем еще запись SPACE,
                    # если машина была более 30 секунд непонятно где
                    if point_info['time_in'] - previous_point['time_out'] \
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
                            previous_point['params']['odoMeter'] = \
                                previous_point['params']['odoMeter'] + \
                                point_info['params']['odoMeter']
                            # сливы, заправки, время движения и стоянки и моточасы не обновляем,
                            # они тянутся ниже
                            continue
                    except IndexError:
                        pass

                unit_info['points'].append(point_info)
                self.previous_point_name = point_name

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

                time_until_value = row['c'][1]['t']\
                    if isinstance(row['c'][1], dict) else row['c'][1]

                if 'unknown' in time_until_value.lower():
                    time_until = data['date_end']
                else:
                    time_until = utc_to_local_time(
                        parse_wialon_report_datetime(time_until_value),
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

            for row in report_data['unit_chronology']:
                row_data = row['c']
                if row_data[0].lower() not in ('parking', 'стоянка', 'остановка'):
                    continue

                time_from = utc_to_local_time(
                    parse_wialon_report_datetime(
                        row_data[1]['t']
                        if isinstance(row_data[1], dict)
                        else row_data[1]
                    ),
                    request.user.ura_tz
                )

                time_until_value = row_data[2]['t']\
                    if isinstance(row_data[2], dict) else row_data[2]

                if 'unknown' in time_until_value.lower():
                    time_until = data['date_end']
                else:
                    time_until = utc_to_local_time(
                        parse_wialon_report_datetime(time_until_value),
                        request.user.ura_tz
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

            # если маршрут начался позже начала смены
            if unit_info['points'] and unit_info['date_begin'] < unit_info['points'][0]['time_in']:
                first_point = unit_info['points'][0]
                first_space_point = dict(
                    name='SPACE',
                    time_in=unit_info['date_begin'],
                    time_out=first_point['time_in'],
                    params=OrderedDict((
                        ('startFuelLevel', first_point['params']['startFuelLevel']),
                        ('endFuelLevel', first_point['params']['startFuelLevel']),
                        ('fuelRefill', .0),
                        ('fuelDrain', .0),
                        ('stopMinutes', .0),
                        ('moveMinutes', .0),
                        ('motoHours', 0),
                        ('odoMeter', 0)
                    )))

                unit_info['points'].insert(0, first_space_point)

            units.append(unit_info)

        return XMLResponse('ura/moving.xml', context)
