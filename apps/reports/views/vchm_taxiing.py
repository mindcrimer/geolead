import datetime
from collections import OrderedDict
import re

import xlwt
from django.db.models import Q
from django.db.models.query import Prefetch

from base.exceptions import ReportException
from moving.service import MovingService
from reports import forms, DEFAULT_OVERSTATEMENT_NORMAL_PERCENTAGE
from snippets.jinjaglobals import date as date_format, floatcomma
from reports.utils import local_to_utc_time, format_timedelta, utc_to_local_time
from reports.views.base import BaseVchmReportView, WIALON_NOT_LOGINED, WIALON_USER_NOT_FOUND
from ura.models import Job, StandardJobTemplate, StandardPoint
from users.models import User
from wialon.api import get_units, get_routes
from wialon.exceptions import WialonException


class VchmTaxiingView(BaseVchmReportView):
    """Суточный отчет для таксировки ПЛ"""
    form_class = forms.VchmTaxiingForm
    template_name = 'reports/vchm_taxiing.html'
    report_name = 'Отчет суточный развернутый по ССМТ для таксировки ПЛ'
    xls_heading_merge = 19

    def __init__(self, *args, **kwargs):
        super(VchmTaxiingView).__init__(*args, **kwargs)
        self.units_dict = {}
        self.user = None

    def get_default_context_data(self, **kwargs):
        context = super(VchmTaxiingView, self).get_default_context_data(**kwargs)
        context.update({
            'overstatement_param': DEFAULT_OVERSTATEMENT_NORMAL_PERCENTAGE
        })
        return context

    def get_default_form(self):
        data = self.request.POST if self.request.method == 'POST' else {
            'dt': datetime.date.today() - datetime.timedelta(days=1),
            'overstatement_param': DEFAULT_OVERSTATEMENT_NORMAL_PERCENTAGE
        }
        return self.form_class(data)

    def get_car_number(self, unit_name):
        unit = self.units_dict.get(unit_name, {})
        return unit.get('number', unit.get('name', ''))

    def get_car_vin(self, unit_name):
        unit = self.units_dict.get(unit_name, {})
        return unit.get('vin', '')

    def get_car_type(self, unit_name):
        unit = self.units_dict.get(unit_name, {})
        return unit.get('vehicle_type', '')

    @staticmethod
    def get_car_model(unit_name):
        return ' '.join(unit_name.split(' ')[:-1])

    @staticmethod
    def get_point_name(point_name):
        if point_name and point_name.lower() != 'space':
            return re.sub(r'[(\[].*?[)\]]', '', point_name)
        return 'Неизвестная'

    @staticmethod
    def get_odometer(unit, visit):
        return getattr(visit, 'total_distance', .0)

    @staticmethod
    def get_fuel_delta(unit, visit):
        start, end = getattr(visit, 'end_fuel_level'), getattr(visit, 'start_fuel_level')
        if start is None or end is None:
            return .0

        return end - start

    @staticmethod
    def render_faults(unit, visit):
        # TODO рассчитывать большие промежутки в сообщениях, координатах, ДУТ,
        # TODO завязанный на моточасы
        return 'OK'

    def get_context_data(self, **kwargs):
        kwargs = super(VchmTaxiingView, self).get_context_data(**kwargs)
        form = kwargs['form']

        sess_id = self.request.session.get('sid')
        if not sess_id:
            raise ReportException(WIALON_NOT_LOGINED)

        try:
            units_list = get_units(sess_id, extra_fields=True)
        except WialonException as e:
            raise ReportException(str(e))

        kwargs['units'] = units_list

        if self.request.POST:

            if form.is_valid():
                report_data = []
                stats = {
                    'dt_from_min': None,
                    'dt_to_max': None,
                    'total_time': .0,
                    'moving_time': .0,
                    'parking_time': .0,
                    'idle_time': .0,
                    'idle_off_time': .0,
                    'angle_sensor_time': .0,
                    'over_3min_parkings_count': 0,
                    'odometer': .0,
                    'fuel_level_delta': .0,
                    'refills_delta': .0,
                    'discharge_delta': .0,
                    'overstatement_mileage': .0,
                    'overstatement_time': .0
                }
                kwargs.update(
                    report_data=report_data,
                    stats=stats
                )

                self.user = User.objects.filter(is_active=True) \
                    .filter(wialon_username=self.request.session.get('user')).first()
                if not self.user:
                    raise ReportException(WIALON_USER_NOT_FOUND)

                local_dt_from = datetime.datetime.combine(
                    form.cleaned_data['dt'],
                    datetime.time(0, 0, 0)
                )
                local_dt_to = datetime.datetime.combine(
                    form.cleaned_data['dt'],
                    datetime.time(23, 59, 59)
                )

                unit_id = form.cleaned_data.get('unit')
                self.units_dict = OrderedDict(
                    (x['name'], x) for x in units_list if x['id'] == unit_id
                )
                unit = list(self.units_dict.values())[0]

                routes = {x['id']: x for x in get_routes(sess_id, with_points=True)}
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

                service = MovingService(
                    self.user,
                    local_dt_from,
                    local_dt_to,
                    sess_id,
                    object_id=unit_id,
                    units_dict=self.units_dict
                )
                service.exec_report()
                service.analyze()

                ura_user = self.user.ura_user if self.user.ura_user_id else self.user
                jobs = Job.objects.filter(
                    user=ura_user,
                    date_begin__gte=local_to_utc_time(local_dt_from, ura_user.timezone),
                    date_end__lte=local_to_utc_time(local_dt_to, ura_user.timezone)
                )
                jobs_cache = {int(j.unit_id): j for j in jobs}

                normal_ratio = 1 + (
                    form.cleaned_data.get(
                        'overstatement_param',
                        DEFAULT_OVERSTATEMENT_NORMAL_PERCENTAGE
                    ) / 100.0
                )

                unit_report_data = service.report_data.get(unit['name'])
                if not unit_report_data:
                    return kwargs

                kwargs.update(heading_data=OrderedDict((
                    ('Марка, модель', self.get_car_model(unit['name'])),
                    ('Гос.номер', self.get_car_number(unit['name'])),
                    ('VIN', self.get_car_vin(unit['name'])),
                    ('Тип ТС', self.get_car_type(unit['name'])),
                    ('Дата', date_format(form.cleaned_data['dt'], 'd.m.Y'))
                )))

                job = jobs_cache.get(unit['id'])
                standard = None
                if job:
                    standard = standards.get(int(job.route_id))

                for visit in unit_report_data.geozones.target:
                    point_standard = None
                    if standard:
                        point_standard = standard.get('points', {}).get(visit.geozone_full, {})
                        if not point_standard:
                            point_standard = standard.get('points', {}).get(visit.geozone, {})

                    total_standart = parking_standard = None
                    if point_standard:
                        total_standart = point_standard['total_time_standard'] * 60
                        parking_standard = point_standard['parking_time_standard'] * 60

                    total_delta = (visit.dt_to - visit.dt_from).total_seconds()
                    parking_delta = getattr(visit, 'parkings_delta', .0)
                    moving_delta = getattr(visit, 'trips_delta', .0)
                    motohours_delta = getattr(visit, 'motohours_delta', .0)
                    idle_delta = getattr(visit, 'idle_delta', .0)
                    off_delta = min(.0, total_delta - motohours_delta)
                    angle_sensor_delta = getattr(visit, 'angle_sensor_delta', .0)
                    refillings_volume = getattr(visit, 'refillings_volume', .0)
                    discharges_volume = getattr(visit, 'discharges_volume', .0)

                    over_3min_parkings_count = len([
                        True for x in getattr(visit, 'parkings', [])
                        if (x.dt_to - x.dt_from).total_seconds() > 3 * 60
                    ])

                    overstatement_time = .0
                    if total_standart is not None \
                            and total_delta / total_standart > normal_ratio:
                        overstatement_time += total_delta - total_standart

                    elif parking_standard is not None \
                            and parking_delta / parking_standard > normal_ratio:
                        overstatement_time += parking_delta - parking_standard

                    report_row = {
                        'car_number': self.get_car_number(unit['name']),
                        'driver_fio': job.driver_fio
                        if job and job.driver_fio else 'Неизвестный',
                        'route_name': job.route_title
                        if job and job.route_title else 'Неизвестный маршрут',
                        'point_name': self.get_point_name(visit.geozone),
                        'dt_from': visit.dt_from,
                        'dt_to': visit.dt_to,
                        'total_time': total_delta,
                        'moving_time': moving_delta,
                        'parking_time': parking_delta,
                        'idle_time': idle_delta,
                        'idle_off_time': off_delta,
                        'angle_sensor_time': angle_sensor_delta,
                        'over_3min_parkings_count': over_3min_parkings_count,
                        'odometer': self.get_odometer(unit, visit),
                        'fuel_level_delta': self.get_fuel_delta(unit, visit),
                        'refills_delta': refillings_volume,
                        'discharge_delta': discharges_volume,
                        'overstatement_mileage': .0,
                        'overstatement_time': overstatement_time,
                        'faults': self.render_faults(unit, visit)
                    }
                    report_data.append(report_row)

                    if stats['dt_from_min'] is None:
                        stats['dt_from_min'] = visit.dt_from
                    else:
                        stats['dt_from_min'] = min(stats['dt_from_min'], visit.dt_from)

                    if stats['dt_to_max'] is None:
                        stats['dt_to_max'] = visit.dt_to
                    else:
                        stats['dt_to_max'] = max(stats['dt_to_max'], visit.dt_to)

                    stats['total_time'] += total_delta
                    stats['moving_time'] += moving_delta
                    stats['parking_time'] += parking_delta
                    stats['idle_time'] += idle_delta
                    stats['idle_off_time'] += off_delta
                    stats['angle_sensor_time'] += angle_sensor_delta
                    stats['over_3min_parkings_count'] += over_3min_parkings_count
                    stats['odometer'] += self.get_odometer(unit, visit)
                    stats['fuel_level_delta'] += self.get_fuel_delta(unit, visit)
                    stats['refills_delta'] += refillings_volume
                    stats['discharge_delta'] += discharges_volume
                    stats['overstatement_mileage'] += .0
                    stats['overstatement_time'] += overstatement_time

        return kwargs

    def write_xls_data(self, worksheet, context):
        worksheet = super(VchmTaxiingView, self).write_xls_data(worksheet, context)

        self.styles.update({
            'border_bold_left_style': xlwt.easyxf(
                'font: bold 1, height 200;'
                'borders: bottom thin, left thin, right thin, top thin;'
                'align: wrap on, vert centre, horiz left'
            ),
            'border_bold_right_style': xlwt.easyxf(
                'font: bold 1, height 200;'
                'borders: bottom thin, left thin, right thin, top thin;'
                'align: wrap on, vert centre, horiz right'
            )
        })

        worksheet.col(0).width = 3600
        worksheet.col(1).width = 5500
        worksheet.col(2).width = 5500
        worksheet.col(3).width = 5500
        worksheet.col(4).width = 3000
        worksheet.col(5).width = 3000
        worksheet.col(6).width = 3150
        worksheet.col(7).width = 3150
        worksheet.col(8).width = 3200
        worksheet.col(9).width = 3200
        worksheet.col(10).width = 3800
        worksheet.col(11).width = 3300
        worksheet.col(12).width = 4500
        worksheet.col(13).width = 3300
        worksheet.col(14).width = 3300
        worksheet.col(15).width = 3300
        worksheet.col(16).width = 3300
        worksheet.col(17).width = 3300
        worksheet.col(18).width = 3300
        worksheet.col(19).width = 7000

        # header
        x = 0
        if context.get('heading_data'):
            for key, value in context['heading_data'].items():
                x += 1
                worksheet.write(x, 0, key + ' ', style=self.styles['right_center_style'])
                worksheet.write_merge(
                    x, x, 1, self.xls_heading_merge - 1, value,
                    style=self.styles['left_center_style']
                )
            x += 1
            worksheet.write_merge(x, x, 0, self.xls_heading_merge, '')

        headings = (
            'Гос № ТС',
            'ФИО водителя',
            'Наименование маршрута',
            'Наименование\nгеозоны',
            'Время\nвхода в\nгеозону',
            'Время\nвыхода из\nгеозоны',
            'Время\nнахождения\nв геозоне,\nчч:мм',
            'Время\nв движении\nв рамках\nгеозоны,\nчч:мм',
            'Время\nпростоя\nв рамках\nгеозоны,\nчч:мм',
            'Время\nпростоя\nна холостом\nходу, чч:мм',
            'Время\nпростоя\nс выключенным\nдвигателем,\nчч:мм',
            'Время\nпростоя\nво время\nработы КМУ,\nчч:мм',
            'Количество\nпростоев с\nдлительностью\n> 3 минут',
            'Пробег\nв рамках\nгеозоны,\nкм',
            'Расход\nтоплива\nв рамках\nгеозоны,\nл',
            'Заправка\nв рамках\nгеозоны,\nл',
            'Слив в\nрамках\nгеозоны,\nл',
            'Перепробег\nпо маршрутам,\nкм',
            'Перепростой\nпо маршрутам,\nч',
            'Исправность оборудования'
        )

        x += 1
        for y, heading in enumerate(headings):

            worksheet.write(
                x, y, heading, style=self.styles['border_center_style']
            )

        worksheet.row(x).height = 1200

        stats = context.get('stats')
        if stats:
            x += 1
            worksheet.write_merge(
                x, x, 0, 3, 'ИТОГО за смену', style=self.styles['border_bold_left_style']
            )
            worksheet.write(
                x, 4, date_format(
                    utc_to_local_time(stats['dt_from_min'], self.user.timezone),
                    'H:i'
                ),
                style=self.styles['border_bold_left_style']
            )
            worksheet.write(
                x, 5, date_format(
                    utc_to_local_time(stats['dt_to_max'], self.user.timezone),
                    'H:i'
                ),
                style=self.styles['border_bold_left_style']
            )
            worksheet.write(
                x, 6, format_timedelta(stats['total_time']),
                style=self.styles['border_bold_left_style']
            )
            worksheet.write(
                x, 7, format_timedelta(stats['moving_time']),
                style=self.styles['border_bold_left_style']
            )
            worksheet.write(
                x, 8, format_timedelta(stats['parking_time']),
                style=self.styles['border_bold_left_style']
            )
            worksheet.write(
                x, 9, format_timedelta(stats['idle_time']),
                style=self.styles['border_bold_left_style']
            )
            worksheet.write(
                x, 10, format_timedelta(stats['idle_off_time']),
                style=self.styles['border_bold_left_style']
            )
            worksheet.write(
                x, 11, format_timedelta(stats['angle_sensor_time']),
                style=self.styles['border_bold_left_style']
            )
            worksheet.write(
                x, 12, stats['over_3min_parkings_count'],
                style=self.styles['border_bold_right_style']
            )
            worksheet.write(
                x, 13, floatcomma(stats['odometer'], -2),
                style=self.styles['border_bold_right_style']
            )
            worksheet.write(
                x, 14, floatcomma(stats['fuel_level_delta'], -2),
                style=self.styles['border_bold_right_style']
            )
            worksheet.write(
                x, 15, floatcomma(stats['refills_delta'], -2),
                style=self.styles['border_bold_right_style']
            )
            worksheet.write(
                x, 16, floatcomma(stats['discharge_delta'], -2),
                style=self.styles['border_bold_right_style']
            )
            worksheet.write(
                x, 17, floatcomma(stats['overstatement_mileage'], -2),
                style=self.styles['border_bold_right_style']
            )
            worksheet.write(
                x, 18, format_timedelta(stats['overstatement_time']),
                style=self.styles['border_bold_left_style']
            )
            worksheet.write(x, 19, '', style=self.styles['border_left_style'])
            worksheet.row(x).height = 360

        for row in context['report_data']:
            x += 1
            worksheet.write(
                x, 0, row['car_number'],
                style=self.styles['border_left_style']
            )
            worksheet.write(
                x, 1, row['driver_fio'],
                style=self.styles['border_left_style']
            )
            worksheet.write(
                x, 2, row['route_name'],
                style=self.styles['border_left_style']
            )
            worksheet.write(
                x, 3, row['point_name'],
                style=self.styles['border_left_style']
            )
            worksheet.write(
                x, 4, date_format(utc_to_local_time(row['dt_from'], self.user.timezone), 'H:i'),
                style=self.styles['border_left_style']
            )
            worksheet.write(
                x, 5, date_format(utc_to_local_time(row['dt_to'], self.user.timezone), 'H:i'),
                style=self.styles['border_left_style']
            )
            worksheet.write(
                x, 6, format_timedelta(row['total_time']),
                style=self.styles['border_left_style']
            )
            worksheet.write(
                x, 7, format_timedelta(row['moving_time']),
                style=self.styles['border_left_style']
            )
            worksheet.write(
                x, 8, format_timedelta(row['parking_time']),
                style=self.styles['border_left_style']
            )
            worksheet.write(
                x, 9, format_timedelta(row['idle_time']),
                style=self.styles['border_left_style']
            )
            worksheet.write(
                x, 10, format_timedelta(row['idle_off_time']),
                style=self.styles['border_left_style']
            )
            worksheet.write(
                x, 11, format_timedelta(row['angle_sensor_time']),
                style=self.styles['border_left_style']
            )
            worksheet.write(
                x, 12, row['over_3min_parkings_count'],
                style=self.styles['border_right_style']
            )
            worksheet.write(
                x, 13, floatcomma(row['odometer'], -2),
                style=self.styles['border_right_style']
            )
            worksheet.write(
                x, 14, floatcomma(row['fuel_level_delta'], -2),
                style=self.styles['border_right_style']
            )
            worksheet.write(
                x, 15, floatcomma(row['refills_delta'], -2),
                style=self.styles['border_right_style']
            )
            worksheet.write(
                x, 16, floatcomma(row['discharge_delta'], -2),
                style=self.styles['border_right_style']
            )
            worksheet.write(
                x, 17, floatcomma(row['overstatement_mileage'], -2),
                style=self.styles['border_right_style']
            )
            worksheet.write(
                x, 18, format_timedelta(row['overstatement_time']),
                style=self.styles['border_left_style']
            )
            worksheet.write(
                x, 19, row['faults'],
                style=self.styles['border_left_style']
            )
            worksheet.row(x).height = 720

        return worksheet
