# -*- coding: utf-8 -*-
import datetime
import traceback
from collections import OrderedDict

from base.exceptions import ReportException, APIProcessError
from base.utils import get_distance, get_point_type, parse_float
from reports.utils import get_period, cleanup_and_request_report, exec_report, get_report_rows, \
    get_wialon_report_template_id, parse_wialon_report_datetime, local_to_utc_time
from snippets.utils.email import send_trigger_email
from ura.lib.resources import URAResource
from ura.models import JobPoint
from ura.utils import parse_datetime, parse_xml_input_data
from wialon.api import get_routes, get_messages
from wialon.auth import get_wialon_session_key
from wialon.exceptions import WialonException


class BaseUraRidesView(URAResource):
    model_mapping = {
        'date_begin': ('dateBegin', parse_datetime),
        'date_end': ('dateEnd', parse_datetime),
        'unit_id': ('idUnit', int),
    }

    def __init__(self, **kwargs):
        super(BaseUraRidesView, self).__init__(**kwargs)
        self.current_distance = .0
        self.input_data = None
        self.job = None
        self.messages = []
        self.report_template_id = None
        self.request_dt_from = None
        self.request_dt_to = None
        self.report_data = {}
        self.fuel_data = OrderedDict()
        self.route = None
        self.route_point_names = []
        self.script_time_from = None
        self.sess_id = None
        self.unit_id = None
        self.unit_zones_visit = []
        self.ride_points = []

    def pre_view_trigger(self, request, **kwargs):
        super(BaseUraRidesView, self).pre_view_trigger(request, **kwargs)
        self.sess_id = get_wialon_session_key(request.user)

    def get_input_data(self, elem):
        self.input_data = parse_xml_input_data(self.request, self.model_mapping, elem)
        return self.input_data

    def get_job(self, **kwargs):
        raise NotImplementedError

    def get_geozones_report_template_id(self):
        self.report_template_id = get_wialon_report_template_id('geozones', self.request.user)
        if self.report_template_id is None:
            raise APIProcessError(
                'Не указан ID шаблона отчета по геозонам у текущего пользователя',
                code='geozones_report_not_found'
            )
        return self.report_template_id

    def get_route(self):
        routes_list = get_routes(sess_id=self.sess_id, with_points=True)
        routes_dict = {x['id']: x for x in routes_list}

        try:
            self.route = routes_dict[int(self.job.route_id)]
        except (ValueError, KeyError):
            raise APIProcessError(
                'Маршрут id=%s не найден среди известных маршрутов' % self.job.route_id
            )

        self.route_point_names = [x['name'] for x in self.route['points']] if self.route else []

        return self.route

    def get_report_data_tables(self):
        raise NotImplementedError

    def get_report_data(self):
        self.get_report_data_tables()

        self.request_dt_from, self.request_dt_to = get_period(
            self.input_data['date_begin'],
            self.input_data['date_end']
        )

        cleanup_and_request_report(
            self.request.user, self.report_template_id, item_id=self.unit_id, sess_id=self.sess_id)

        try:
            r = exec_report(
                self.request.user,
                self.report_template_id,
                self.request_dt_from,
                self.request_dt_to,
                object_id=self.unit_id,
                sess_id=self.sess_id
            )
        except ReportException as e:
            raise WialonException(
                'Не удалось получить в Wialon отчет о поездках: %s' % e
            )

        for table_index, table_info in enumerate(r['reportResult']['tables']):
            if table_info['name'] not in self.report_data:
                continue

            try:
                rows = get_report_rows(
                    self.request.user,
                    table_index,
                    table_info['rows'],
                    level=1,
                    sess_id=self.sess_id
                )

                if table_info['name'] != 'unit_sensors_tracing':
                    self.report_data[table_info['name']] = rows
                else:
                    for row in rows:
                        if isinstance(row['c'][0], dict):
                            key = row['c'][0]['v']
                        else:
                            key = parse_wialon_report_datetime(row['c'][0])
                            key = int(
                                local_to_utc_time(key, self.request.user.wialon_tz).timestamp()
                            )
                        if key and row['c'][1]:
                            self.fuel_data[key] = parse_float(row['c'][1]) or .0

            except ReportException as e:
                raise WialonException(
                    'Не удалось получить в Wialon отчет о поездках. Исходная ошибка: %s' % e
                )

    def get_object_messages(self):
        self.messages = list(filter(
            lambda x: x['pos'] is not None,
            get_messages(
                self.unit_id, self.request_dt_from, self.request_dt_to, sess_id=self.sess_id
            )['messages']
        ))

        return self.messages

    def prepare_geozones_visits(self):
        # удаляем лишнее
        self.report_data['unit_zones_visit'] = tuple(map(
            lambda x: x['c'], self.report_data['unit_zones_visit']
        ))

        # удаляем геозоны, которые нас не интересуют
        try:
            self.report_data['unit_zones_visit'] = tuple(filter(
                lambda pr: pr[0].strip() in self.route_point_names,
                self.report_data['unit_zones_visit']
            ))
        except AttributeError as e:
            send_trigger_email(
                'Ошибка в работе интеграции Wialon', extra_data={
                    'Exception': str(e),
                    'Traceback': traceback.format_exc(),
                    'data': self.report_data['unit_zones_visit'],
                    'body': self.request.body
                }
            )

        # пробегаемся по интервалам геозон и сглаживаем их
        self.unit_zones_visit = []
        for i, row in enumerate(self.report_data['unit_zones_visit']):
            if isinstance(row[2], str):
                # если конец участка неизвестен, считаем, что конец участка - конец периода запроса
                row[2] = {'v': self.request_dt_to}

            geozone_name = row[0]['t'] if isinstance(row[0], dict) else row[0]
            row = {
                'name': geozone_name.strip(),
                'time_in': row[1]['v'],
                'time_out': row[2]['v']
            }

            # проверим интервалы между отрезками
            try:
                previous_geozone = self.unit_zones_visit[-1]
                # если время входа в текущую не превышает 1 минуту выхода из предыдущей
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

                    # если же объект вылетел из геозоны в другую менее чем на 1 минуту
                    # (то есть проехал в текущей геозоне менее 1 минуты) - списываем на помехи
                    if row['time_out'] - row['time_in'] < 60:
                        # и при этом в дальнейшем вернется в предыдущую:
                        try:
                            next_geozone = self.report_data['unit_zones_visit'][i + 1]
                            if next_geozone[0].strip() == previous_geozone['name']:
                                # то игнорируем текущую геозону, будто ее и не было,
                                # расширив по диапазону времени предыдущую
                                previous_geozone['time_out'] = row['time_out']
                                continue
                        except IndexError:
                            pass

            except IndexError:
                pass

            self.unit_zones_visit.append(row)

        if self.unit_zones_visit:
            # обработаем концевые участки: сигнал с объекта мог не успеть прийти в начале
            # и конце диапазона запроса, поэтому если сигнал не приходил в приемлимое время
            # (3 минуты), считаем, что объект там и находился
            delta = 60 * 3
            if self.unit_zones_visit[0]['time_in'] - self.request_dt_from < delta:
                self.unit_zones_visit[0]['time_in'] = self.request_dt_from

            # добавляем SPACE, так как точное местоположение на момент начала смены неизвестно
            elif self.unit_zones_visit[0]['time_in'] - self.request_dt_from > 0:

                # если первая точка уже SPACE, просто расширяем ее период до начала смены
                if self.unit_zones_visit[0]['name'].lower() == 'space':
                    self.unit_zones_visit[0]['time_in'] = self.request_dt_from

                # иначе добавляем SPACE
                else:
                    self.unit_zones_visit.insert(0, {
                        'name': 'SPACE',
                        'time_in': self.request_dt_from,
                        'time_out': self.unit_zones_visit[0]['time_in']
                    })

            if self.request_dt_to - self.unit_zones_visit[-1]['time_out'] < delta:
                self.unit_zones_visit[-1]['time_out'] = self.request_dt_to

    def get_fuel_level(self, message):
        timestamp = message['t']
        if timestamp in self.fuel_data:
            return self.fuel_data[timestamp]

        t = 0
        for t in self.fuel_data.keys():
            if t >= timestamp:
                return self.fuel_data[t]

        # берем последнее известное
        if t:
            return self.fuel_data[t]

        return .0

    def start_timer(self):
        self.script_time_from = datetime.datetime.now()

    def process_messages(self):
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
                        self.add_new_point(message, prev_message, geozone)
                        current_geozone = geozone

                    found_geozone = True
                    break

            if prev_message:
                self.current_distance += prev_message['distance']

            if not found_geozone:
                if self.ride_points and self.ride_points[-1]['name'] == 'SPACE':
                    self.ride_points[-1]['time_out'] = message['t']
                    self.ride_points[-1]['params']['odoMeter'] = self.current_distance
                else:
                    current_geozone = {
                        'name': 'SPACE'
                    }
                    self.add_new_point(message, prev_message, {
                        'name': current_geozone['name'],
                        'time_in': message['t'],
                        'time_out': message['t']
                    })

            # если сообщение последнее, то закрываем пробег последнего участка
            if i == messages_length0:
                fuel_level = round(self.get_fuel_level(message), 2)
                self.ride_points[-1]['params']['endFuelLevel'] = fuel_level
                self.ride_points[-1]['params']['odoMeter'] = \
                    self.current_distance
            prev_message = message

        self.print_time_needed('Points build')

    def update_job_points_cache(self):
        """Обновляем кэш пройденных точек"""
        self.job.points.all().delete()
        for point in self.ride_points:
            time_in = point['time_in']
            time_out = point['time_out']

            jp = JobPoint(
                job=self.job,
                title=point['name'],
                point_type=get_point_type(point['name']),
                enter_date_time=time_in,
                leave_date_time=time_out,
                total_time=(time_out - time_in).total_seconds(),
                parking_time=point['params']['stopMinutes'],
                lat=point['coords']['lat'],
                lng=point['coords']['lng']
            )

            jp.save()

    def add_new_point(self, message, prev_message, geozone):
        fuel_level = round(self.get_fuel_level(message), 2)

        new_point = {
            'name': geozone['name'],
            'time_in': geozone['time_in'],
            'time_out': geozone['time_out'],
            'type': get_point_type(geozone['name']),
            'params': OrderedDict((
                ('startFuelLevel', fuel_level),
                ('endFuelLevel', .0),
                ('fuelRefill', .0),
                ('fuelDrain', .0),
                ('stopMinutes', .0),
                ('moveMinutes', .0),
                ('motoHours', .0),
                ('odoMeter', .0)
            )),
            'coords': {
                'lat': message.get('pos', {}).get('y', None),
                'lng': message.get('pos', {}).get('x', None)
            }
        }

        # закрываем пробег и топливо на конец участка для предыдущей точки
        if prev_message:
            fuel_level = round(self.get_fuel_level(prev_message), 2)
        else:
            fuel_level = .0

        try:
            previous_geozone = self.ride_points[-1]
            previous_geozone['time_out'] = geozone['time_in']
            previous_geozone['params']['odoMeter'] = self.current_distance
            previous_geozone['params']['endFuelLevel'] = fuel_level
        except IndexError:
            pass

        # сбрасываем пробег
        self.current_distance = .0

        self.ride_points.append(new_point)

    def print_time_needed(self, message=''):
        # print(
        #     '%s: %s' % (
        #         message,
        #         ((datetime.datetime.now() - self.script_time_from).microseconds / 1000)
        #     )
        # )
        pass
