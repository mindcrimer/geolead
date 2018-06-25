from collections import OrderedDict
import datetime
import re
import time
import traceback

from django.db.models import Prefetch, Q

from base.exceptions import ReportException, APIProcessError
from base.utils import parse_float
from reports import forms, DEFAULT_TOTAL_TIME_STANDARD_MINUTES, \
    DEFAULT_PARKING_TIME_STANDARD_MINUTES, DEFAULT_OVERSTATEMENT_NORMAL_PERCENTAGE
from reports.utils import local_to_utc_time, cleanup_and_request_report, \
    get_wialon_report_template_id, exec_report, get_report_rows, format_timedelta, \
    utc_to_local_time, parse_wialon_report_datetime
from reports.views.base import BaseVchmReportView, WIALON_NOT_LOGINED, WIALON_USER_NOT_FOUND
from snippets.jinjaglobals import date as date_format
from snippets.utils.email import send_trigger_email
from ura.models import StandardJobTemplate, StandardPoint, Job
from users.models import User
from wialon.api import get_units, get_routes
from wialon.exceptions import WialonException


class VchmIdleTimesView(BaseVchmReportView):
    """Отчет по простоям за смену"""
    form_class = forms.VchmIdleTimesForm
    template_name = 'reports/vchm_idle_times.html'
    report_name = 'Отчет по простоям за смену'
    xls_heading_merge = 12

    def __init__(self, *args, **kwargs):
        super(VchmIdleTimesView, self).__init__(*args, **kwargs)
        self.units_dict = {}

    def get_default_context_data(self, **kwargs):
        context = super(VchmIdleTimesView, self).get_default_context_data(**kwargs)
        context.update({
            'default_total_time_standard': DEFAULT_TOTAL_TIME_STANDARD_MINUTES,
            'default_parking_time_standard': DEFAULT_PARKING_TIME_STANDARD_MINUTES,
            'overstatement_param': DEFAULT_OVERSTATEMENT_NORMAL_PERCENTAGE
        })
        return context

    def get_default_form(self):
        data = self.request.POST if self.request.method == 'POST' else {
            'dt_from': datetime.date.today() - datetime.timedelta(days=1),
            'dt_to': datetime.date.today() - datetime.timedelta(days=1),
            'default_total_time_standard': DEFAULT_TOTAL_TIME_STANDARD_MINUTES,
            'default_parking_time_standard': DEFAULT_PARKING_TIME_STANDARD_MINUTES,
            'overstatement_param': DEFAULT_OVERSTATEMENT_NORMAL_PERCENTAGE
        }
        return self.form_class(data)

    def get_car_number(self, unit_id):
        return self.units_dict.get(int(unit_id), {}).get('number', '')

    def get_car_vin(self, unit_id):
        return self.units_dict.get(int(unit_id), {}).get('vin', '')

    def get_car_type(self, unit_id):
        return self.units_dict.get(int(unit_id), {}).get('vehicle_type', '')

    @staticmethod
    def get_geozones_report_template_id(user):
        report_template_id = get_wialon_report_template_id('geozones', user)
        if report_template_id is None:
            raise APIProcessError(
                'Не указан ID шаблона отчета по геозонам у текущего пользователя',
                code='geozones_report_not_found'
            )
        return report_template_id

    @staticmethod
    def prepare_geozones_visits(user, geozones_report_data, route_point_names, dt_from, dt_to):
        # удаляем лишнее
        geozones_report_data['unit_zones_visit'] = tuple(map(
            lambda x: x['c'], geozones_report_data['unit_zones_visit']
        ))

        # удаляем геозоны, которые нас не интересуют
        try:
            geozones_report_data['unit_zones_visit'] = tuple(filter(
                lambda pr: pr[0].strip() in route_point_names,
                geozones_report_data['unit_zones_visit']
            ))
        except AttributeError as e:
            send_trigger_email(
                'Ошибка в работе интеграции Wialon', extra_data={
                    'Exception': str(e),
                    'Traceback': traceback.format_exc(),
                    'data': geozones_report_data['unit_zones_visit'],
                    'user': user
                }
            )

        # пробегаемся по интервалам геозон и сглаживаем их
        unit_zones_visit = []
        prev_odometer = .0
        for i, row in enumerate(geozones_report_data['unit_zones_visit']):
            if isinstance(row[2], str):
                # если конец участка неизвестен, считаем, что конец участка - конец периода запроса
                row[2] = {'v': dt_to}

            try:
                odometer = parse_float(row[4])
            except IndexError:
                odometer = prev_odometer

            geozone_name = row[0]['t'] if isinstance(row[0], dict) else row[0]
            try:
                row = {
                    'name': geozone_name.strip(),
                    'time_in': row[1]['v'],
                    'time_out': row[2]['v'],
                    'odometer_from': prev_odometer,
                    'odometer_to': odometer
                }
            except (IndexError, KeyError, ValueError, AttributeError) as e:
                send_trigger_email(
                    'Нет необходимого атрибута v в результате', extra_data={
                        'Exception': str(e),
                        'Traceback': traceback.format_exc(),
                        'row': row,
                        'user': user
                    }
                )

            # проверим интервалы между отрезками
            try:
                previous_geozone = unit_zones_visit[-1]
                # если время входа в текущую не превышает 1 минуту выхода из предыдущей
                delta = row['time_in'] - previous_geozone['time_out']
                if 0 < delta < 60:
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
                            next_geozone = geozones_report_data['unit_zones_visit'][i + 1]
                            if next_geozone[0].strip() == previous_geozone['name']:
                                # то игнорируем текущую геозону, будто ее и не было,
                                # расширив по диапазону времени предыдущую
                                previous_geozone['time_out'] = row['time_out']
                                continue
                        except IndexError:
                            pass
                elif delta > 0:
                    # добавим SPACE перед текущей точкой
                    unit_zones_visit.append({
                        'name': 'SPACE',
                        'time_in': previous_geozone['time_out'],
                        'time_out': row['time_in'],
                        'odometer_from': previous_geozone['odometer_to'],
                        'odometer_to': row['odometer_from']
                    })
            except IndexError:
                pass

            prev_odometer = odometer
            unit_zones_visit.append(row)

        if unit_zones_visit:
            # обработаем концевые участки: сигнал с объекта мог не успеть прийти в начале
            # и конце диапазона запроса, поэтому если сигнал не приходил в приемлимое время
            # (3 минуты), считаем, что объект там и находился
            delta = 60 * 3
            if unit_zones_visit[0]['time_in'] - dt_from < delta:
                unit_zones_visit[0]['time_in'] = dt_from

            elif unit_zones_visit[0]['time_in'] - dt_from > 0:

                # если первая точка уже SPACE, просто расширяем ее период до начала смены
                if unit_zones_visit[0]['name'].lower() == 'space':
                    unit_zones_visit[0]['time_in'] = dt_from

                # иначе добавляем SPACE
                else:
                    unit_zones_visit.insert(0, {
                        'name': 'SPACE',
                        'time_in': dt_from,
                        'time_out': unit_zones_visit[0]['time_in'],
                        'odometer_from': 0,
                        'odometer_to': unit_zones_visit[0]['odometer_from']
                    })

            if dt_to - unit_zones_visit[-1]['time_out'] < delta:
                unit_zones_visit[-1]['time_out'] = dt_to

        for row in geozones_report_data['unit_chronology']:
            row_data = row['c']
            if not isinstance(row_data[0], str):
                send_trigger_email(
                    'В хронологии первое поле отчета не строка!', extra_data={
                        'row_data': row_data,
                        'user': user
                    }
                )
                continue

            time_from = utc_to_local_time(
                parse_wialon_report_datetime(
                    row_data[1]['t']
                    if isinstance(row_data[1], dict)
                    else row_data[1]
                ),
                user.ura_tz
            )

            time_until_value = row_data[2]['t'] \
                if isinstance(row_data[2], dict) else row_data[2]

            if 'unknown' in time_until_value.lower():
                time_until = dt_to
            else:
                time_until = utc_to_local_time(
                    parse_wialon_report_datetime(time_until_value),
                    user.ura_tz
                )

            for point in self.ride_points:
                if point['time_in'] > time_until:
                    # дальнейшие строки точно не совпадут (виалон все сортирует по дате)
                    break

                # если интервал точки меньше даты начала хронологии, значит еще не дошли
                if point['time_out'] < time_from:
                    continue

                delta = min(time_until, point['time_out']) - max(time_from, point['time_in'])
                # не пересекаются:
                if delta.total_seconds() < 0:
                    continue

                if row_data[0].lower() in ('поездка', 'trip'):
                    point['params']['moveMinutes'] += delta.total_seconds()
                elif row_data[0].lower() in ('стоянка', 'parking'):
                    self.add_stop(point, time_from, time_until, row_data[3])

        return unit_zones_visit

    @staticmethod
    def get_point_name(point_name):
        if point_name and point_name.lower() != 'space':
            return re.sub(r'[(\[].*?[)\]]', '', point_name)
        return 'Неизвестная'

    def get_context_data(self, **kwargs):
        kwargs = super(VchmIdleTimesView, self).get_context_data(**kwargs)
        report_data = None
        form = kwargs['form']

        sess_id = self.request.session.get('sid')
        if not sess_id:
            raise ReportException(WIALON_NOT_LOGINED)

        try:
            units_list = get_units(sess_id=sess_id, extra_fields=True)
        except WialonException as e:
            raise ReportException(str(e))

        kwargs['units'] = units_list

        if self.request.POST:

            if form.is_valid():
                report_data = []
                geozones_report_data = {
                    'unit_chronology': [],
                    'unit_digital_sensors': [],
                    'unit_engine_hours': [],
                    'unit_zones_visit': []
                }

                user = User.objects.filter(is_active=True) \
                    .filter(wialon_username=self.request.session.get('user')).first()
                if not user:
                    raise ReportException(WIALON_USER_NOT_FOUND)

                dt_from = local_to_utc_time(datetime.datetime.combine(
                    form.cleaned_data['dt_from'],
                    datetime.time(0, 0, 0)
                ), user.wialon_tz)
                dt_to = local_to_utc_time(datetime.datetime.combine(
                    form.cleaned_data['dt_to'],
                    datetime.time(23, 59, 59)
                ), user.wialon_tz)

                routes = {
                    x['id']: x for x in get_routes(sess_id=sess_id, user=user, with_points=True)
                }
                self.units_dict = OrderedDict((x['id'], x) for x in units_list)
                selected_unit = form.cleaned_data.get('unit')

                if selected_unit and selected_unit in self.units_dict:
                    self.units_dict = {
                        selected_unit: self.units_dict[selected_unit]
                    }

                standard_job_templates = StandardJobTemplate.objects \
                    .filter(wialon_id__in=[str(x) for x in routes.keys()]) \
                    .prefetch_related(
                        Prefetch(
                            'points',
                            StandardPoint.objects.filter(
                                Q(total_time_standard__isnull=False) |
                                Q(parking_time_standard__isnull=False)
                            ),
                            'points_cache'
                        )
                    )

                standards = {
                    int(x.wialon_id): {
                        'space_overstatements_standard': x.space_overstatements_standard
                        if x.space_overstatements_standard is not None else None,
                        'points': {
                            p.title: {
                                'total_time_standard': p.total_time_standard
                                if p.total_time_standard is not None else None,
                                'parking_time_standard': p.parking_time_standard
                                if p.parking_time_standard is not None else None
                            } for p in x.points_cache
                        }
                    } for x in standard_job_templates
                    if x.space_overstatements_standard is not None or x.points_cache
                }

                ura_user = user.ura_user if user.ura_user_id else user
                jobs = Job.objects\
                    .filter(user=ura_user, date_begin__gte=dt_from, date_end__lte=dt_to)\
                    .order_by('date_begin', 'date_end')
                jobs_cache = {int(j.unit_id): j for j in jobs}

                normal_ratio = 1 + (
                    form.cleaned_data.get(
                        'overstatement_param',
                        DEFAULT_OVERSTATEMENT_NORMAL_PERCENTAGE
                    ) / 100.0
                )
                total_count = len(self.units_dict)
                i = 0
                for unit in self.units_dict.values():
                    i += 1
                    print('%s/%s: %s' % (i, total_count, unit['name']))
                    job = jobs_cache.get(unit['id'])
                    standard = None
                    if job:
                        standard = standards.get(int(job.route_id))

                    report_template_id = self.get_geozones_report_template_id(user)
                    cleanup_and_request_report(
                        user, report_template_id, item_id=unit['id'], sess_id=sess_id
                    )

                    request_dt_from = int(time.mktime(dt_from.timetuple()))
                    request_dt_to = int(time.mktime(dt_to.timetuple()))

                    try:
                        r = exec_report(
                            user,
                            report_template_id,
                            request_dt_from,
                            request_dt_to,
                            object_id=unit['id'],
                            sess_id=sess_id
                        )
                    except ReportException as e:
                        raise WialonException(
                            'Не удалось получить в Wialon отчет о поездках: %s' % e
                        )

                    for table_index, table_info in enumerate(r['reportResult']['tables']):
                        if table_info['name'] not in geozones_report_data:
                            continue

                        try:
                            geozones_report_data[table_info['name']] = get_report_rows(
                                user,
                                table_index,
                                table_info['rows'],
                                level=1,
                                sess_id=sess_id
                            )

                        except ReportException as e:
                            raise WialonException(
                                'Не удалось получить в Wialon отчет о поездках.'
                                'Исходная ошибка: %s' % e
                            )

                    try:
                        route = routes[int(job.route_id) if job else -1]
                    except KeyError:
                        fixed_routes = [
                            x for x in routes.values() if 'фиксир' in x['name'].lower()
                        ]
                        route = fixed_routes[0] if fixed_routes else {'points': []}

                    route_point_names = [x['name'] for x in route['points']] if route else []

                    unit_zones_visits = self.prepare_geozones_visits(
                        user, geozones_report_data, route_point_names,
                        request_dt_from, request_dt_to
                    )

                    for point in unit_zones_visits:
                        point_standard = {}
                        if standard:
                            point_standard = standard.get('points', {}).get(point['name'], {})

                        if not point_standard.get('total_time_standard'):
                            point_standard['total_time_standard'] = form.cleaned_data.get(
                                'default_total_time_standard',
                                DEFAULT_TOTAL_TIME_STANDARD_MINUTES
                            )
                        if not point_standard.get('parking_time_standard'):
                            point_standard['parking_time_standard'] = form.cleaned_data.get(
                                'default_parking_time_standard',
                                DEFAULT_PARKING_TIME_STANDARD_MINUTES
                            )

                        total_standart = point_standard['total_time_standard'] * 60
                        parking_standard = point_standard['parking_time_standard'] * 60

                        overstatement = .0
                        total_time = point['time_out'] - point['time_in']
                        parking_time = point.get('parking_time', .0)
                        if total_standart is not None \
                                and total_time / total_standart > normal_ratio:
                            overstatement += total_time - total_standart

                        elif parking_standard is not None \
                                and parking_time / parking_standard > normal_ratio:
                            overstatement += parking_time - parking_standard

                        if overstatement > .0:
                            row = dict()
                            row['driver_fio'] = job.driver_fio \
                                if job and job.driver_fio else 'Неизвестный'
                            row['car_number'] = self.get_car_number(unit['id'])
                            row['car_vin'] = self.get_car_vin(unit['id'])
                            row['car_type'] = self.get_car_type(unit['id'])
                            row['route_name'] = job.route_title \
                                if job and job.route_title else 'Неизвестный маршрут'
                            row['point_name'] = self.get_point_name(point['name'])

                            row['total_time'] = total_time
                            row['parking_time'] = .0
                            row['off_motor_time'] = .0
                            row['idle_time'] = .0
                            row['gpm_time'] = .0
                            row['stops'] = ''

                            row['overstatement'] = round(overstatement)
                            report_data.append(row)

            kwargs.update(
                report_data=report_data
            )

        return kwargs

    def write_xls_data(self, worksheet, context):
        worksheet = super(VchmIdleTimesView, self).write_xls_data(worksheet, context)

        worksheet.col(0).width = 5500
        worksheet.col(1).width = 3000
        worksheet.col(2).width = 5000
        worksheet.col(3).width = 5000
        worksheet.col(4).width = 6000
        worksheet.col(5).width = 7000
        worksheet.col(6).width = 3150
        worksheet.col(7).width = 3150
        worksheet.col(8).width = 3700
        worksheet.col(9).width = 3700
        worksheet.col(10).width = 3300
        worksheet.col(11).width = 7000
        worksheet.col(12).width = 3600

        headings = (
            'Водитель',
            'Гос №',
            'VIN',
            'Тип ТС',
            'Название маршрута',
            'Название геозоны',
            'Время\nнахождения,\nчч:мм',
            'Время\nостановки,\nчч:мм',
            'Время\nс выключенным\nдвигателем, чч:мм',
            'Время на\nхолостом ходу\n(без работы), чч:мм',
            'Время работы\nГПМ,\nчч:мм',
            'Место остановки\n(адрес или км трассы)',
            'Время простоя\nсверх норматива*,\nчч:мм'
        )

        # header
        worksheet.write_merge(
            1, 1, 0, 16, 'За период: %s - %s' % (
                date_format(context['cleaned_data']['dt_from'], 'd.m.Y'),
                date_format(context['cleaned_data']['dt_to'], 'd.m.Y')
            )
        )

        x = 2
        for y, heading in enumerate(headings):
            worksheet.write(
                x, y, heading, style=self.styles['border_center_style']
            )

        worksheet.row(x).height = 900

        for row in context['report_data']:
            x += 1
            worksheet.write(
                x, 0, row['driver_fio'],
                style=self.styles['border_left_style']
            )
            worksheet.write(
                x, 1, row['car_number'],
                style=self.styles['border_left_style']
            )
            worksheet.write(
                x, 2, row['car_vin'],
                style=self.styles['border_left_style']
            )
            worksheet.write(
                x, 3, row['car_type'],
                style=self.styles['border_left_style']
            )
            worksheet.write(
                x, 4, row['route_name'],
                style=self.styles['border_left_style']
            )
            worksheet.write(
                x, 5, row['point_name'],
                style=self.styles['border_left_style']
            )
            worksheet.write(
                x, 6, format_timedelta(row['total_time']),
                style=self.styles['border_right_style']
            )
            worksheet.write(
                x, 7, format_timedelta(row['parking_time']),
                style=self.styles['border_right_style']
            )
            worksheet.write(
                x, 8, format_timedelta(row['off_motor_time']),
                style=self.styles['border_right_style']
            )
            worksheet.write(
                x, 9, format_timedelta(row['idle_time']),
                style=self.styles['border_right_style']
            )
            worksheet.write(
                x, 10, format_timedelta(row['gpm_time']),
                style=self.styles['border_right_style']
            )
            worksheet.write(
                x, 11, row['stops'] or '',
                style=self.styles['border_left_style']
            )
            worksheet.write(
                x, 12, format_timedelta(row['overstatement']),
                style=self.styles['border_right_style']
            )
            worksheet.row(x).height = 520

        x += 1
        worksheet.write_merge(
            x, x, 0, self.xls_heading_merge,
            '*В случае превышения фактического простоя над нормативным более чем на %s%%' %
            context['cleaned_data'].get(
                'overstatement_param', DEFAULT_OVERSTATEMENT_NORMAL_PERCENTAGE
            ),
            style=self.styles['left_center_style']
        )
        worksheet.row(x).height = 520

        return worksheet
