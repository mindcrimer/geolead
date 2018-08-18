from collections import OrderedDict
import datetime
import re
import time

from pytz import utc

from base.utils import get_distance
from moving.casting import IntersectionPeriod, IntersectionMoment
from moving.casting.motohours import Motohours
from moving.casting.odometer import OdometerRow
from moving.report_mapping import MOVING_SERVICE_MAPPING, ReportUnit
from moving.casting.visits import Visit
from reports.utils import get_wialon_report_template_id, local_to_utc_time, \
    cleanup_and_request_report, exec_report, get_report_rows
from ura.models import Job
from wialon.api import get_units, get_routes, get_messages


class MovingService(object):
    """Сервис получения данных о движение объекта"""

    def __init__(self, user, local_dt_from, local_dt_to, sess_id, object_id=None,
                 units_dict=None, tables=None, calc_odometer=True, calc_idle=True,
                 first_visit_allowance=60 * 3, last_visit_allowance=60 * 3,
                 devide_last_parking_by_motohours=False):
        self.user = user
        self.local_dt_from = local_dt_from
        self.local_dt_to = local_dt_to
        self.utc_dt_from = local_to_utc_time(local_dt_from, self.user.timezone)
        self.utc_dt_to = local_to_utc_time(local_dt_to, self.user.timezone)
        self.utc_timestamp_from = int(time.mktime(self.utc_dt_from.timetuple()))
        self.utc_timestamp_to = int(time.mktime(self.utc_dt_to.timetuple()))

        self.object_id = object_id
        self.sess_id = sess_id

        self.mobile_vehicle_types = set()
        self.calc_odometer = calc_odometer
        self.calc_idle = calc_idle
        # допущения в секундах для первого и последнего визита, если больше, то вставляется space
        self.first_visit_allowance = first_visit_allowance
        self.last_visit_allowance = last_visit_allowance
        self.devide_last_parking_by_motohours = devide_last_parking_by_motohours

        self.tables = []
        all_tables = [x['name'] for x in MOVING_SERVICE_MAPPING.values() if x['level'] > 0]
        if tables is not None:
            assert isinstance(tables, (list, dict, set))
            self.tables = list(filter(lambda x: x in all_tables, tables))
        else:
            self.tables = all_tables

        if units_dict is None:
            units_list = get_units(sess_id)
            self.units_dict = {u['name']: u for u in units_list}
        else:
            self.units_dict = units_dict

        self.report_data = OrderedDict()
        for unit in self.units_dict.values():
            self.report_data[unit['name']] = ReportUnit(unit)

        if self.user.wialon_mobile_vehicle_types:
            self.mobile_vehicle_types = set(
                x.strip() for x in self.user.wialon_mobile_vehicle_types.lower().split(',')
            )

        self.script_time_from = datetime.datetime.now()

        self.jobs_cache = {}
        self.routes_cache = {}
        self.init_caches()

    def init_caches(self):
        ura_user = self.user.ura_user if self.user.ura_user_id else self.user
        jobs = Job.objects.filter(
            user=ura_user,
            date_begin__gte=self.utc_dt_from,
            date_end__lte=self.utc_dt_to
        )

        if len(self.units_dict) < 10:
            jobs = jobs.filter(unit_id__in=[str(x['id']) for x in self.units_dict.values()])

        self.jobs_cache = {int(j.unit_id): j for j in jobs}
        self.routes_cache = {
            x['id']: x for x in get_routes(self.sess_id, with_points=True)
        }
        self.print_time_needed('Init caches')

    def print_time_needed(self, message=''):
        print(
            '%s: %.2f' % (
                message,
                ((datetime.datetime.now() - self.script_time_from).total_seconds() * 1000)
            )
        )
        self.script_time_from = datetime.datetime.now()

    def exec_report(self):
        template_id = get_wialon_report_template_id('taxiing', self.user, self.sess_id)

        cleanup_and_request_report(self.user, template_id, self.sess_id)
        report = exec_report(
            self.user, template_id, self.sess_id, self.utc_timestamp_from, self.utc_timestamp_to,
            object_id=self.object_id
        )
        self.print_time_needed('Exec report')

        for table_index, table_info in enumerate(report['reportResult']['tables']):
            label = table_info['label'].lower()
            if label not in MOVING_SERVICE_MAPPING:
                continue

            mapping = MOVING_SERVICE_MAPPING[label]

            name = mapping['name']
            if name not in self.tables:
                continue

            level = mapping['level']
            renderer = mapping['renderer']

            rows = get_report_rows(
                self.sess_id,
                table_index,
                table_info['rows'],
                level=level
            )

            for row in rows:
                unit_key = row['c'][0].strip()
                if unit_key not in self.units_dict:
                    continue

                unit_obj = self.report_data[unit_key]

                params = {
                    'tz': self.user.timezone
                }
                data = renderer([row['c']] if level < 2 else [x['c'] for x in row['r']], **params)
                getattr(unit_obj, name).extend_source(data)

        self.print_time_needed('Parse report')

    @staticmethod
    def prepare_geozone_name(geozone_name):
        return re.sub(r'[(\[].*?[)\]]', '', geozone_name).strip()

    def get_visits(self, unit):
        assert 'geozones' in self.tables

        unit_name = unit['name']
        geozones = self.report_data[unit_name].geozones.source
        visits = self.report_data[unit_name].geozones.target
        job = self.jobs_cache.get(unit['id'])

        is_fixed_route = False
        try:
            route = self.routes_cache[int(job.route_id) if job else -1]
        except KeyError:
            fixed_routes = [
                x for x in self.routes_cache.values() if 'фиксир' in x['name'].lower()
            ]
            route = fixed_routes[0] if fixed_routes else {'points': []}
            is_fixed_route = True
        else:
            if 'фиксир' in route['name'].lower():
                is_fixed_route = True

        route_point_names = {
            self.prepare_geozone_name(x['name']) for x in route['points']
        } if route else set()

        # удаляем геозоны, которые нас не интересуют
        geozones = tuple(filter(
            lambda geozone_row: self.prepare_geozone_name(
                geozone_row.geozone.strip()
            ) in route_point_names,
            geozones
        ))

        # пробегаемся по интервалам геозон и сглаживаем их
        for i, row in enumerate(geozones):
            if not is_fixed_route and job:
                delta = (
                    min(row.dt_to, job.date_end) - max(row.dt_from, job.date_begin)
                ).total_seconds()

                if delta <= 0:
                    continue

            visit = Visit(
                self.prepare_geozone_name(row.geozone), row.dt_from, row.dt_to,
                geozone_full=row.geozone.strip()
            )

            # проверим интервалы между отрезками
            try:
                previous_visit = visits[-1]

                # если время входа в текущую не превышает 1 минуту выхода из предыдущей
                delta = (visit.dt_from - previous_visit.dt_to).total_seconds()
                if 0 < delta <= 60:
                    # если имена совпадают
                    if visit.geozone == previous_visit.geozone:
                        # тогда прибавим к предыдущей геозоне
                        previous_visit.dt_to = visit.dt_to
                        continue
                    else:
                        # или же просто предыдущей точке удлиняем время выхода (или усреднять?)
                        previous_visit.dt_to = visit.dt_from

                    # если же объект вылетел из геозоны в другую менее чем на 1 минуту
                    # (то есть проехал в текущей геозоне менее 1 минуты) - списываем на помехи
                    if (visit.dt_to - visit.dt_from).total_seconds() < 60:
                        # и при этом в дальнейшем вернется в предыдущую:
                        try:
                            next_geozone = geozones[i + 1]
                            if next_geozone.geozone == previous_visit.geozone:
                                # то игнорируем текущую геозону, будто ее и не было,
                                # расширив по диапазону времени предыдущую
                                previous_visit.dt_to = visit.dt_to
                                continue
                        except IndexError:
                            pass

                elif delta > 60:
                    # добавим SPACE перед текущей точкой
                    visits.append(Visit(
                        'SPACE',
                        previous_visit.dt_to,
                        visit.dt_from
                    ))
                elif previous_visit.geozone == visit.geozone:
                    # если промежутка нет, и геозоны одинаковые, то сливаем в одну
                    previous_visit.dt_to = visit.dt_to
                    continue

            except IndexError:
                pass

            visits.append(visit)

        if visits:
            first_visit = visits[0]
            # обработаем концевые участки: сигнал с объекта мог не успеть прийти в начале
            # и конце диапазона запроса, поэтому если сигнал не приходил в приемлимое время
            # (3 минуты), считаем, что объект там и находился
            first_visit_delta = (first_visit.dt_from - self.utc_dt_from).total_seconds()
            if first_visit_delta < self.first_visit_allowance:
                first_visit.dt_from = self.utc_dt_from

            elif first_visit_delta > 0:
                # если первая точка уже SPACE, просто расширяем ее период до начала смены
                if first_visit.geozone == 'SPACE':
                    first_visit.dt_from = self.utc_dt_from

                # иначе добавляем SPACE
                else:
                    visits.insert(0, Visit(
                        'SPACE',
                        self.utc_dt_from,
                        first_visit.dt_from,
                    ))

            last_visit = visits[-1]
            if last_visit:

                # если включен режим разбивки последней стоянке по последним моточасам:
                if self.devide_last_parking_by_motohours:
                    motohours = None
                    try:
                        motohours = getattr(self.report_data[unit_name], 'motohours').source[-1]
                    except (IndexError, AttributeError):
                        pass

                    if motohours:
                        if last_visit.dt_from < motohours.dt_to < last_visit.dt_to:
                            visits.insert(-1, Visit(
                                last_visit.geozone,
                                last_visit.dt_from,
                                motohours.dt_to,
                                last_visit.geozone_full
                            ))
                            # так как visit - это nameptuple, то придется целиком заменить его
                            visits[-1] = Visit(
                                last_visit.geozone,
                                motohours.dt_to,
                                last_visit.dt_to,
                                last_visit.geozone_full
                            )
                            last_visit = visits[-1]

                last_delta = (self.utc_dt_to - last_visit.dt_to).total_seconds()
                if last_delta < self.last_visit_allowance:
                    visits[-1] = Visit(
                        last_visit.geozone,
                        last_visit.dt_from,
                        self.utc_dt_to,
                        last_visit.geozone_full
                    )

                elif last_delta > 0:
                    # если большая дельта в конце, добавляем SPACE
                    visits.append(Visit(
                        'SPACE',
                        last_visit.dt_to,
                        self.utc_dt_to
                    ))

        else:
            # если ничего не найдено, отдаем полный SPACE
            visits.append(Visit(
                'SPACE',
                self.utc_dt_from,
                self.utc_dt_to,
            ))

        self.report_data[unit_name].geozones.target_analyzed = True

    def set_intersection_periods(self, source, target, target_field=None, delta_field=None):
        """
        :param source: таблица, откуда берутся временные периоды
        :param target: таблица, в которой на искомые интервалы присваиваются найденные периоды
        :param target_field: поле цели, в которое пишутся периоды
        :param delta_field: поле цели, которое увеличивается на продолжительность
        найденного периода
        :return: None
        """
        for row in source:
            dt_from, dt_to = row.dt_from, row.dt_to
            if not dt_to:
                dt_to = self.utc_dt_to

            for col in target:
                if target_field and not hasattr(col, target_field):
                    setattr(col, target_field, [])

                if delta_field and not hasattr(col, delta_field):
                    setattr(col, delta_field, .0)

                if col.dt_from > dt_to:
                    # дальнейшие строки точно не совпадут (виалон все сортирует по дате)
                    break

                # если интервал точки меньше даты начала хронологии, значит еще не дошли
                if col.dt_to < dt_from:
                    continue

                min_to, max_from = min(dt_to, col.dt_to), max(dt_from, col.dt_from)
                delta = (min_to - max_from).total_seconds()

                # не пересекаются:
                if delta <= 0:
                    continue

                if target_field:
                    getattr(col, target_field).append(IntersectionPeriod(row, max_from, min_to))

                if delta_field:
                    setattr(col, delta_field, getattr(col, delta_field) + delta)

    @staticmethod
    def set_intersection_moments(source, target, target_field=None, volume_source_field=None,
                                 volume_target_field=None, break_on_suitable=True):
        """
        :param source: таблица, откуда берутся временные точки (моменты)
        :param target: таблица, в которой на искомые интервалы присваиваются найденные моменты
        :param target_field: поле цели, в которое пишутся моменты
        :param volume_source_field: поле источника, которое будет суммироваться
        в volume_target_field
        :param volume_target_field: поле цели, которое увеличивается на объем найденного момента
        :param break_on_suitable: прерывает поиск при нахождении искомого интервала визита
        :return: None
        """
        for row in source:
            for col in target:
                if target_field and not hasattr(col, target_field):
                    setattr(col, target_field, [])

                if volume_target_field and volume_source_field \
                        and not hasattr(col, volume_target_field):
                    setattr(col, volume_target_field, .0)

                if col.dt_from > row.dt:
                    # дальнейшие строки точно не совпадут (виалон все сортирует по дате)
                    break

                if col.dt_from <= row.dt <= col.dt_to:

                    volume = .0
                    if volume_source_field:
                        volume = getattr(row, volume_source_field)

                    if target_field:
                        getattr(col, target_field).append(IntersectionMoment(row, row.dt, volume))

                    if volume_target_field:
                        setattr(
                            col,
                            volume_target_field,
                            getattr(col, volume_target_field) + volume
                        )
                    # одно событие не может попасть в 2 интервала
                    if break_on_suitable:
                        break

    def get_periods(self, unit):
        unit_name = unit['name']
        visits = self.report_data[unit_name].geozones.target

        period_tables = ('motohours', 'trips', 'parkings', 'angle_sensor')
        for table in period_tables:
            if table in self.tables:
                source = getattr(self.report_data[unit_name], table).source
                self.set_intersection_periods(
                    source, visits, target_field=table, delta_field='%s_delta' % table
                )

        moment_tables = ('refillings', 'discharges')
        for table in moment_tables:
            if table in self.tables:
                source = getattr(self.report_data[unit_name], table).source
                self.set_intersection_moments(
                    source, visits, target_field=table, volume_source_field='volume',
                    volume_target_field='%s_volume' % table
                )

        if 'fuel_level' in self.tables:
            source = getattr(self.report_data[unit_name], 'fuel_level').source
            self.set_intersection_moments(
                source, visits, target_field='fuel_levels', volume_source_field='volume'
            )

            for visit in visits:
                visit.start_fuel_level, visit.end_fuel_level = None, None
                if hasattr(visit, 'fuel_levels') and visit.fuel_levels:
                    visit.start_fuel_level = visit.fuel_levels[0].volume
                    visit.end_fuel_level = visit.fuel_levels[-1].volume
                else:
                    visit.fuel_levels = []

        if self.calc_idle:
            # XX - это включенный двигатель на стоянках за вычетом работы ГПН
            # то есть нужно вычесть из моточасов визитов поездки и работу ГПН
            for visit in visits:
                visit.idle_times = []
                # сначала объединяем периоды поездок и работы ГПН
                work_times = getattr(visit, 'trips', []) + getattr(visit, 'angle_sensor', [])
                motohours = getattr(visit, 'motohours', [])

                # затем вычитаем эти периоды из периодов моточасов
                for motohour in motohours:
                    motohour_periods = [Motohours(motohour.dt_from, motohour.dt_to)]

                    for work in work_times:
                        to_delete, to_append = [], []
                        for i, mh in enumerate(motohour_periods):
                            delta = (
                                min(work.dt_to, mh.dt_to) - max(work.dt_from, mh.dt_from)
                            ).total_seconds()

                            if delta > 0:
                                if work.dt_from <= mh.dt_from and work.dt_to >= mh.dt_to:
                                    # если исключаемый период равен или накрывает целиком моточасы
                                    to_delete.append(i)
                                    # если равен, то можно не продолжать
                                    if work.dt_from == mh.dt_from and work.dt_to == mh.dt_to:
                                        break

                                elif work.dt_from >= mh.dt_from and work.dt_to <= mh.dt_to:
                                    # если исключаемый объект полностью внутри моточасов
                                    # если концы пересекаются:
                                    if work.dt_from == mh.dt_from:
                                        mh.dt_from = work.dt_to
                                    elif work.dt_to == mh.dt_to:
                                        mh.dt_to = work.dt_from
                                    else:
                                        # если полностью внутри, то разрезаем период на два
                                        to_delete.append(i)
                                        to_append.extend([
                                            Motohours(mh.dt_from, work.dt_from),
                                            Motohours(work.dt_to, mh.dt_to)
                                        ])
                                else:
                                    if work.dt_to < mh.dt_to:
                                        mh.dt_from = work.dt_to
                                    if work.dt_from > mh.dt_from:
                                        mh.dt_to = work.dt_from

                        if to_delete:
                            motohour_periods = list(map(lambda x: x[1], filter(
                                lambda x: x[0] not in to_delete,
                                enumerate(motohour_periods)
                            )))
                        motohour_periods.extend(to_append)
                    visit.idle_times.extend(motohour_periods)
                visit.idle_delta = sum([
                    (x.dt_to - x.dt_from).total_seconds() for x in visit.idle_times
                ])

    def get_object_messages(self, unit):
        return list(filter(
            lambda x: x['pos'] is not None,
            get_messages(
                unit['id'], self.utc_timestamp_from, self.utc_timestamp_to, self.sess_id
            )['messages']
        ))

    def get_odometer(self, unit):
        unit_name = unit['name']
        visits = self.report_data[unit_name].geozones.target
        odometer_table = self.report_data[unit_name].odometer
        messages = self.get_object_messages(unit)
        # сделаем обычную таблицу моментов (dt / volume), и потом внедрим ее в таблицу визитов
        prev_message = None
        total_odometer = .0

        for i, message in enumerate(messages):
            distance = .0
            if prev_message:
                # получаем пройденное расстояние для предыдущей точки
                # TODO: попробовать через geopy
                distance = get_distance(
                    prev_message['pos']['x'],
                    prev_message['pos']['y'],
                    message['pos']['x'],
                    message['pos']['y']
                )
            dt = datetime.datetime.fromtimestamp(message['t']).replace(tzinfo=utc)
            total_odometer += distance
            odometer_table.append_source(OdometerRow(dt, total_odometer))
            prev_message = message

        # а затем рассчитаем показатель на вход и на выход из геозоны
        self.set_intersection_moments(
            odometer_table.source, visits, target_field='odometers', volume_source_field='value',
            break_on_suitable=False
        )
        for visit in visits:
            visit.start_odometer, visit.end_odometer, visit.total_distance = None, None, .0
            if hasattr(visit, 'odometers') and visit.odometers:
                visit.start_odometer = visit.odometers[0].volume
                visit.end_odometer = visit.odometers[-1].volume
                visit.total_distance = visit.end_odometer - visit.start_odometer
            else:
                visit.odometers = []

    def analyze(self):
        total = len(self.units_dict)
        for i, unit in enumerate(self.units_dict.values(), start=1):
            unit_name = unit['name']
            if not self.report_data.get(unit_name):
                continue

            print('%s/%s) Unit %s started' % (i, total, unit['name']))
            self.get_visits(unit)
            self.get_periods(unit)
            if self.calc_odometer:
                self.get_odometer(unit)

            self.print_time_needed('%s/%s) Unit %s processed' % (i, total, unit['name']))
