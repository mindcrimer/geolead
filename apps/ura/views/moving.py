# -*- coding: utf-8 -*-
from collections import OrderedDict
from copy import deepcopy
import datetime

from base.exceptions import ReportException
from base.utils import parse_float
from reports.utils import parse_wialon_report_datetime, utc_to_local_time, get_period, \
    cleanup_and_request_report, get_wialon_geozones_report_template_id, exec_report, \
    get_report_rows, parse_timedelta
from snippets.utils.datetime import utcnow
from ura import models
from ura.lib.resources import URAResource
from ura.lib.response import XMLResponse, error_response
from ura.utils import parse_datetime, parse_xml_input_data, float_format
from ura.wialon.api import get_routes_list
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
                            previous_point['params']['odoMeter'] = point_info['params'][
                                'odoMeter']
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
                            previous_point = unit_info['points'][i - 1]
                        except IndexError:
                            pass

                    try:
                        next_point = unit_info['points'][i + 1]
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

                point['params']['moveMinutes'] = round(
                    point['params']['moveMinutes'] / 60.0, 2
                )
                point['params']['stopMinutes'] = round(
                    point['params']['stopMinutes'] / 60.0, 2
                )
                point['params']['motoHours'] = round(
                    point['params']['motoHours'] / 3600.0, 2
                )

            units.append(unit_info)

        return XMLResponse('ura/moving.xml', context)
