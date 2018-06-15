import datetime

from django.db.models import Prefetch, Q

from base.exceptions import ReportException
from reports import forms
from reports.jinjaglobals import date
from reports.utils import local_to_utc_time, utc_to_local_time
from reports.views.base import BaseVchmReportView, WIALON_NOT_LOGINED, WIALON_USER_NOT_FOUND
from ura.models import StandardJobTemplate, StandardPoint, Job, JobPoint
from users.models import User
from wialon.api import get_units, get_routes
from wialon.exceptions import WialonException


class VchmIdleTimesView(BaseVchmReportView):
    """Отчет по простоям за смену"""
    form_class = forms.VchmIdleTimesForm
    template_name = 'reports/vchm_idle_times.html'
    report_name = 'Отчет по простоям за смену'
    xls_heading_merge = 11

    def __init__(self, *args, **kwargs):
        super(VchmIdleTimesView, self).__init__(*args, **kwargs)
        self.units_dict = {}

    def get_default_form(self):
        data = self.request.POST if self.request.method == 'POST' else {
            'dt_from': datetime.date.today() - datetime.timedelta(days=1),
            'dt_to': datetime.date.today() - datetime.timedelta(days=1),
            'default_total_time_standard': 3,
            'default_parking_time_standard': 3
        }
        return self.form_class(data)

    @staticmethod
    def get_new_grouping():
        return {
            'driver_fio': '',
            'car_number': '',
            'car_vin': '',
            'car_type': '',
            'route_name': '',
            'point_name': '',
            'parking_time': '',
            'off_motor_time': '',
            'idle_time': '',
            'gpm_time': '',
            'address': '',
            'overstatement': ''
        }

    def get_car_number(self, unit_id):
        return self.units_dict.get(int(unit_id), {}).get('number', '')

    def get_car_vin(self, unit_id):
        return self.units_dict.get(int(unit_id), {}).get('vin', '')

    def get_car_type(self, unit_id):
        return self.units_dict.get(int(unit_id), {}).get('vehicle_type', '')

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
                self.units_dict = {x['id']: x for x in get_units(user=user, sess_id=sess_id)}

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
                    .prefetch_related(
                        Prefetch(
                            'points', JobPoint.objects.order_by('id'), to_attr='cached_points'
                        )
                    )\
                    .order_by('date_begin', 'date_end')

                normal_ratio = 1 + (form.cleaned_data['overstatement_param'] / 100.0)

                for job in jobs:
                    spaces_total_time = .0
                    spaces = []
                    standard = standards.get(int(job.route_id))

                    for point in job.cached_points:

                        if point.title.lower() == 'space':
                            spaces.append(point)
                            spaces_total_time += point.total_time

                        point_standard = None
                        if standard:
                            point_standard = standard.get('points', {}).get(point.title)

                        if not point_standard:
                            point_standard = {
                                'total_time_standard': form.cleaned_data.get(
                                    'default_total_time_standard', 3
                                ),
                                'parking_time_standard': form.cleaned_data.get(
                                    'default_parking_time_standard', 3
                                )
                            }

                        overstatement = .0
                        total_time = point.total_time / 60.0
                        if point_standard['total_time_standard'] is not None \
                                and total_time / point_standard['total_time_standard'] \
                                > normal_ratio:
                            overstatement += total_time - point_standard['total_time_standard']

                        parking_time = point.parking_time / 60.0
                        if point_standard['parking_time_standard'] is not None \
                                and parking_time / point_standard['parking_time_standard'] \
                                > normal_ratio:
                            overstatement += parking_time \
                                             - point_standard['parking_time_standard']

                        if overstatement > .0:
                            row = self.get_new_grouping()
                            row['driver_fio'] = job.driver_fio \
                                if job.driver_fio else 'Неизвестный'
                            row['car_number'] = self.get_car_number(job.unit_id)
                            row['car_vin'] = self.get_car_vin(job.unit_id)
                            row['car_type'] = self.get_car_type(job.unit_id)
                            row['route_name'] = job.route_title \
                                if job.route_title else 'Неизвестный маршрут'
                            row['point_name'] = point.title if point.title else 'Неизвестная'

                            row['parking_time'] = .0
                            row['off_motor_time'] = .0
                            row['idle_time'] = .0
                            row['gpm_time'] = .0
                            row['address'] = .0

                            overstatement = round(overstatement / 60.0, 2) \
                                if overstatement > 1.0 else round(overstatement / 60.0, 4)
                            row['overstatement'] = overstatement

                            report_data.append(row)

                    spaces_total_time /= 60.0
                    if standard and spaces \
                            and standard['space_overstatements_standard'] is not None \
                            and spaces_total_time / standard['space_overstatements_standard'] \
                            > normal_ratio:
                        row = self.get_new_grouping()
                        row['route_id'] = job.route_id
                        row['point_name'] = 'SPACE'
                        row['car_number'] = self.get_car_number(job.unit_id)
                        row['driver_fio'] = job.driver_fio if job.driver_fio else ''
                        row['overstatement'] = round(
                            (
                                spaces_total_time - standard['space_overstatements_standard']
                            ) / 60.0, 2
                        )
                        report_data.append(row)

                report_data = sorted(report_data, key=lambda k: k['fact_period'])

            kwargs.update(
                report_data=report_data,
            )

        return kwargs

    def write_xls_data(self, worksheet, context):
        worksheet = super(VchmIdleTimesView, self).write_xls_data(worksheet, context)

        worksheet.col(0).width = 5000
        worksheet.col(1).width = 5000
        worksheet.col(2).width = 5000
        worksheet.col(3).width = 5000
        worksheet.col(4).width = 5000
        worksheet.col(5).width = 5000
        worksheet.col(6).width = 5000
        worksheet.col(7).width = 5000
        worksheet.col(8).width = 5000
        worksheet.col(9).width = 5000
        worksheet.col(10).width = 5000
        worksheet.col(11).width = 5000

        headings = (
            'Водитель',
            'Гос №',
            'VIN',
            'Тип ТС',
            'Название маршрута',
            'Название геозоны',
            'Время остановки, чч:мм',
            'Время с выключенным двигателем, чч:мм',
            'Время на холостом ходу (без работы), чч:мм',
            'Время работы ГПМ, чч:мм',
            'Место остановки (адрес или км трассы)',
            'Время простоя сверх норматива*, чч:мм'
        )

        x = 1
        for y, heading in enumerate(headings):
            worksheet.write(
                x, y, heading, style=self.styles['border_center_style']
            )

        worksheet.row(x).height = 900

        worksheet.write_merge(x, x, 0, 11, 'В процессе реализации')

        for row in context['report_data']:
            x += 1

        return worksheet
