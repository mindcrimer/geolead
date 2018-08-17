from collections import OrderedDict
import datetime
import re

from django.db.models import Prefetch, Q

import xlwt

from base.exceptions import ReportException
from moving.service import MovingService
from reports import forms, DEFAULT_TOTAL_TIME_STANDARD_MINUTES, \
    DEFAULT_PARKING_TIME_STANDARD_MINUTES, DEFAULT_OVERSTATEMENT_NORMAL_PERCENTAGE
from reports.utils import local_to_utc_time, format_timedelta
from reports.views.base import BaseVchmReportView, WIALON_NOT_LOGINED, WIALON_USER_NOT_FOUND
from snippets.jinjaglobals import date as date_format
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
    def get_point_name(point_name):
        if point_name and point_name.lower() != 'space':
            return re.sub(r'[(\[].*?[)\]]', '', point_name)
        return 'Неизвестная'

    @staticmethod
    def render_parking(parkings):
        if parkings:
            parking = parkings[0]
            url = None

            if parking.row.coords:
                url = 'https://maps.yandex.ru/?text={lat},{lng}'.format(**parking.row.coords)
            if url:
                return xlwt.Formula(
                    'HYPERLINK("%s";"%s")' % (url, parking.row.address or 'Неизвестно')
                )
            else:
                return parking.row.address or 'Неизвестно'
        return ''

    def get_context_data(self, **kwargs):
        kwargs = super(VchmIdleTimesView, self).get_context_data(**kwargs)
        report_data = None
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

                user = User.objects.filter(is_active=True) \
                    .filter(wialon_username=self.request.session.get('user')).first()
                if not user:
                    raise ReportException(WIALON_USER_NOT_FOUND)

                local_dt_from = datetime.datetime.combine(
                    form.cleaned_data['dt_from'],
                    datetime.time(0, 0, 0)
                )
                local_dt_to = datetime.datetime.combine(
                    form.cleaned_data['dt_to'],
                    datetime.time(23, 59, 59)
                )

                selected_unit = form.cleaned_data.get('unit')
                self.units_dict = OrderedDict(
                    (x['name'], x) for x in units_list
                    if not selected_unit or (selected_unit and x['id'] == selected_unit)
                )

                routes = {
                    x['id']: x for x in get_routes(sess_id, with_points=True)
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
                jobs = Job.objects.filter(
                    user=ura_user,
                    date_begin__gte=local_to_utc_time(local_dt_from, ura_user.timezone),
                    date_end__lte=local_to_utc_time(local_dt_to, ura_user.timezone)
                )
                jobs_cache = {int(j.unit_id): j for j in jobs}

                mobile_vehicle_types = set()
                vehtypes = user.wialon_mobile_vehicle_types or ura_user.wialon_mobile_vehicle_types
                if vehtypes:
                    mobile_vehicle_types = set(x.strip() for x in vehtypes.lower().split(','))

                service = MovingService(
                    user,
                    local_dt_from,
                    local_dt_to,
                    sess_id,
                    object_id=selected_unit if selected_unit else None,
                    units_dict=self.units_dict,
                    calc_odometer=False
                )
                service.exec_report()
                service.analyze()

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

                    vehicle_type = unit['vehicle_type'].lower()
                    if mobile_vehicle_types and vehicle_type \
                            and vehicle_type not in mobile_vehicle_types:
                        print('%s) Skip vehicle type "%s" of item %s' % (
                            i, vehicle_type, unit['name']
                        ))
                        continue

                    job = jobs_cache.get(unit['id'])
                    standard = None
                    if job:
                        standard = standards.get(int(job.route_id))

                    unit_report_data = service.report_data.get(unit['name'], {})
                    for visit in unit_report_data.geozones.target:
                        point_standard = {}
                        if standard:
                            point_standard = standard.get('points', {}).get(visit.geozone_full, {})
                            if not point_standard:
                                point_standard = standard.get('points', {}).get(visit.geozone, {})

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
                        total_time = (visit.dt_to - visit.dt_from).total_seconds()
                        parking_time = getattr(visit, 'parkings_delta', .0)
                        if total_standart is not None \
                                and total_time / total_standart > normal_ratio:
                            overstatement += total_time - total_standart

                        elif parking_standard is not None \
                                and parking_time / parking_standard > normal_ratio:
                            overstatement += parking_time - parking_standard

                        if overstatement > .0 and total_time < 86395:  # суточный простой исключаем
                            row = dict()
                            row['driver_fio'] = job.driver_fio \
                                if job and job.driver_fio else 'Неизвестный'
                            row['car_number'] = self.get_car_number(unit['name'])
                            row['car_vin'] = self.get_car_vin(unit['name'])
                            row['car_type'] = self.get_car_type(unit['name'])
                            row['route_name'] = job.route_title \
                                if job and job.route_title else 'Неизвестный маршрут'
                            row['point_name'] = self.get_point_name(visit.geozone)

                            row['total_time'] = total_time
                            row['parking_time'] = parking_time
                            row['off_motor_time'] = max(total_time - getattr(
                                visit, 'motohours_delta', .0
                            ), .0)
                            row['idle_time'] = sum([
                                (x.dt_to - x.dt_from).total_seconds() for x in
                                getattr(visit, 'idle_times', [])
                            ])
                            row['gpm_time'] = getattr(
                                visit, 'angle_sensor_delta', .0
                            )
                            row['parkings'] = getattr(visit, 'parkings', [])

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
            1, 1, 0, self.xls_heading_merge, 'За период: %s - %s' % (
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
                x, 11, self.render_parking(row['parkings']),
                style=self.styles['border_left_style']
            )
            worksheet.write(
                x, 12, format_timedelta(row['overstatement']),
                style=self.styles['border_right_style']
            )
            worksheet.row(x).height = 720

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
