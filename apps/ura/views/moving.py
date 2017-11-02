# -*- coding: utf-8 -*-
import datetime
from collections import OrderedDict

from base.exceptions import ReportException
from base.utils import get_distance, parse_float
from reports.utils import utc_to_local_time, get_period, cleanup_and_request_report, \
    get_wialon_geozones_report_template_id, exec_report, get_report_rows, \
    parse_wialon_report_datetime
from snippets.utils.datetime import utcnow
from ura import models
from ura.lib.resources import URAResource
from ura.lib.response import XMLResponse, error_response
from ura.utils import parse_datetime, parse_xml_input_data
from wialon.api import get_routes, get_messages, get_unit_settings
from wialon.auth import authenticate_at_wialon
from wialon.exceptions import WialonException
from wialon.utils import get_fuel_level


class URAMovingResource(URAResource):
    model_mapping = {
        'date_begin': ('dateBegin', parse_datetime),
        'date_end': ('dateEnd', parse_datetime),
        'unit_id': ('idUnit', int),
    }
    
    def __init__(self, **kwargs):
        super(URAMovingResource, self).__init__(**kwargs)
        self.route = None
        self.unit_info = None
        self.current_distance = .0
        self.calibration_table = []
        self.fuel_level_name = None
        self.script_time_from = None

    def post(self, request, **kwargs):
        units = []

        context = self.get_context_data(**kwargs)
        context.update({
            'now': utcnow(),
            'units': units
        })

        sess_id = authenticate_at_wialon(request.user.wialon_token)
        routes_list = get_routes(sess_id=sess_id, with_points=True)
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

            if job:
                try:
                    self.route = routes_dict.get(int(job.route_id))
                except ValueError:
                    pass

            route_point_names = [x['name'] for x in self.route['points']] \
                if self.route else []

            self.unit_info = {
                'id': unit_id,
                'date_begin': utc_to_local_time(data['date_begin'], request.user.ura_tz),
                'date_end': utc_to_local_time(data['date_end'], request.user.ura_tz),
                'points': []
            }

            dt_from, dt_to = get_period(
                data['date_begin'],
                data['date_end']
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
                'unit_thefts': [],
                'unit_engine_hours': [],
                'unit_zones_visit': [],
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
                        sess_id=sess_id
                    )

                    report_data[table_info['name']] = rows

                except ReportException:
                    raise WialonException('Не удалось извлечь данные о поездке')

            # получаем настройки объекта (машины)
            unit_settings = get_unit_settings(unit_id, sess_id=sess_id)

            messages = list(filter(
                lambda x: x['pos'] is not None,
                get_messages(unit_id, dt_from, dt_to, sess_id=sess_id)['messages']
            ))

            self.script_time_from = datetime.datetime.now()

            # получаем настройки ДУТ
            fuel_level_conf = list(filter(
                lambda x: x['p'].startswith('rs485_'),
                unit_settings['sens'].values()
            ))

            if not fuel_level_conf:
                raise WialonException('Нет данных о настройках датчика уровня топлива')

            fuel_level_conf = fuel_level_conf[0]

            def get_calibration_table_sort_key(item):
                return item['x']

            # сортируем калибровочную таблицу расчета уровня топлива
            self.calibration_table = sorted(
                fuel_level_conf['tbl'],
                key=get_calibration_table_sort_key
            )

            # получаем название ДУТ
            self.fuel_level_name = fuel_level_conf['p']

            # удаляем лишнее
            report_data['unit_zones_visit'] = map(
                lambda x: x['c'], report_data['unit_zones_visit']
            )

            # удаляем геозоны, которые нас не интересуют
            report_data['unit_zones_visit'] = list(filter(
                lambda pr: pr[0].strip() in route_point_names,
                report_data['unit_zones_visit']
            ))

            # пробегаемся по интервалам геозон и сглаживаем их
            unit_zones_visit = []
            for i, row in enumerate(report_data['unit_zones_visit']):
                if isinstance(row[2], str):
                    # если время выхода не указано, то по указанию заказчика считаем, что движение
                    # объекта незакончено на участке, и мы его пропускаем
                    continue

                row = {
                    'name': row[0].strip(),
                    'time_in': row[1]['v'],
                    'time_out': row[2]['v']
                }

                # проверим интервалы между отрезками
                try:
                    previous_geozone = unit_zones_visit[-1]
                    # если время входа в текущую не превышает 1 минуту выхода из предыдщуей
                    delta = row['time_in'] - previous_geozone['time_out']
                    if delta < 60:
                        # если имена совпадают
                        if row['name'] == previous_geozone['name']:
                            # тогда прибавим к предыдущей геозоне
                            previous_geozone['time_out'] = row['time_out']
                            continue
                        else:
                            # или же просто предыдущей точке удлиняем время выхода (или усреднять?)
                            previous_geozone['time_out'] = row['time_in']

                except IndexError:
                    pass

                # если объект вылетел из геозоны в другую менее чем на 1 минуту
                # (то есть проехал в текущей геозоне менее 1 минуты) - списываем на помехи
                if row['time_out'] - row['time_in'] < 60:
                    # и при этом в дальнейшем вернется в предыдущую:
                    try:
                        previous_geozone = unit_zones_visit[-1]
                        next_geozone = report_data['unit_zones_visit'][i + 1]
                        if next_geozone[0].strip() == previous_geozone['name']:
                            # то игнорируем текущую геозону, будто ее и не было,
                            # расширив по диапазону времени предыдущую
                            previous_geozone['time_out'] = row['time_out']
                            continue
                    except IndexError:
                        pass

                unit_zones_visit.append(row)

            if unit_zones_visit:
                # обработаем концевые участки: сигнал с объекта мог не успеть прийти в начале
                # и конце диапазона запроса, поэтому если сигнал не приходил в приемлимое время
                # (1.5 минуты), считаем, что объект там и находился
                delta = 60 * 1.5
                if unit_zones_visit[0]['time_in'] - dt_from < delta:
                    unit_zones_visit[0]['time_in'] = dt_from

                if dt_to - unit_zones_visit[-1]['time_out'] < delta:
                    unit_zones_visit[-1]['time_out'] = dt_to

            prev_message = None
            current_geozone = None
            messages_length0 = len(messages) - 1

            self.print_time_needed('Prepare')

            for i, message in enumerate(messages):
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
                for geozone in unit_zones_visit:

                    # если точка входит по времени в геозону
                    if geozone['time_in'] <= message['t'] <= geozone['time_out']:

                        # и текущая геозона сменилась - закрываем предыдущую, открывая новую
                        if not current_geozone or geozone['name'] != current_geozone['name']:
                            self.add_new_point(message, prev_message, geozone)
                            current_geozone = geozone

                        if prev_message:
                            self.current_distance += prev_message['distance']

                        # если сообщение последнее, то закрываем пробег последнего участка
                        if i == messages_length0:
                            fuel_level = round(self.get_fuel_level(message), 2)
                            self.unit_info['points'][-1]['params']['endFuelLevel'] = fuel_level
                            self.unit_info['points'][-1]['params']['odoMeter'] = \
                                self.current_distance

                        found_geozone = True
                        break

                if not found_geozone:
                    if self.unit_info['points']\
                            and self.unit_info['points'][-1]['name'] == 'SPACE':
                        self.unit_info['points'][-1]['time_out'] = message['t']
                        self.unit_info['points'][-1]['params']['odoMeter'] = self.current_distance
                    else:
                        self.add_new_point(message, prev_message, {
                            'name': 'SPACE',
                            'time_in': message['t'],
                            'time_out': message['t']
                        })
                prev_message = message

            self.print_time_needed('Points build')

            for point in self.unit_info['points']:
                point['time_in'] = utc_to_local_time(
                    datetime.datetime.utcfromtimestamp(point['time_in']),
                    request.user.ura_tz
                )
                point['time_out'] = utc_to_local_time(
                    datetime.datetime.utcfromtimestamp(point['time_out']),
                    request.user.ura_tz
                )

            self.print_time_needed('points utc_to_local')

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

                    for point in self.unit_info['points']:
                        if point['time_in'] <= dt <= point['time_out']:
                            point['params']['fuelDrain'] += volume
                            break

            self.print_time_needed('fuelDrain')

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

                    for point in self.unit_info['points']:
                        if point['time_in'] <= dt <= point['time_out']:
                            point['params']['fuelRefill'] += volume
                            break

            self.print_time_needed('fuelRefill')

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
                    time_until = utc_to_local_time(data['date_end'], request.user.ura_tz)
                else:
                    time_until = utc_to_local_time(
                        parse_wialon_report_datetime(time_until_value),
                        request.user.ura_tz
                    )

                for point in self.unit_info['points']:
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

                for point in self.unit_info['points']:
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

            # преобразуем секунды в минуты и часы
            for i, point in enumerate(self.unit_info['points']):
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

            units.append(self.unit_info)

            self.print_time_needed('Total calc')

        return XMLResponse('ura/moving.xml', context)

    def get_fuel_level(self, message):
        return get_fuel_level(
            self.calibration_table, message['p'][self.fuel_level_name]
        )

    def add_new_point(self, message, prev_message, geozone):
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
            previous_geozone = self.unit_info['points'][-1]
            previous_geozone['time_out'] = geozone['time_in']
            previous_geozone['params']['odoMeter'] = self.current_distance
            previous_geozone['params']['endFuelLevel'] = fuel_level
        except IndexError:
            pass

        # сбрасываем пробег
        self.current_distance = .0

        self.unit_info['points'].append(new_point)

    def print_time_needed(self, message=''):
        print(
            '%s: %s' % (
                message,
                ((datetime.datetime.now() - self.script_time_from).microseconds / 1000)
            )
        )
