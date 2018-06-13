import datetime

from django.db.models import Prefetch, Q

from base.exceptions import ReportException
from base.utils import get_point_type
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
    xls_heading_merge = 7

    def get_default_form(self):
        data = self.request.POST if self.request.method == 'POST' else {
            'dt_from': datetime.date.today() - datetime.timedelta(days=1),
            'dt_to': datetime.date.today() - datetime.timedelta(days=1),
            'default_overstatements_standard': 3
        }
        return self.form_class(data)

    @staticmethod
    def get_new_grouping():
        return {
            'car_number': '',
            'driver_fio': '',
            'fact_period': '',
            'overstatement': '',
            'plan_period': '',
            'point_name': '',
            'point_type': '',
            'route_id': ''
        }

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
                units_dict = {x['id']: x for x in get_units(user=user, sess_id=sess_id)}

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
                    .filter(
                        user=ura_user,
                        date_begin__gte=dt_from,
                        date_end__lte=dt_to,
                        route_id__in=list(routes.keys())
                    )\
                    .prefetch_related(
                        Prefetch(
                            'points', JobPoint.objects.order_by('id'), to_attr='cached_points'
                        )
                    )\
                    .order_by('date_begin', 'date_end')

                def get_car_number(unit_id, _units_dict):
                    return _units_dict.get(int(unit_id), {}).get('number', '')

                normal_ratio = 1 + (form.cleaned_data['overstatement_param'] / 100.0)

                for job in jobs:
                    spaces_total_time = .0
                    spaces = []
                    standard = standards.get(int(job.route_id))
                    if not standard:
                        print('No standards (job id=%s)' % job.pk)
                        continue

                    for point in job.cached_points:

                        if point.title.lower() == 'space':
                            spaces.append(point)
                            spaces_total_time += point.total_time

                        else:
                            point_standard = standard['points'].get(point.title)
                            if not point_standard:
                                continue

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
                                row['fact_period'] = '%s - %s' % (
                                    date(utc_to_local_time(
                                        point.enter_date_time.replace(tzinfo=None),
                                        user.wialon_tz
                                    ), 'd.m.Y H:i:s'),
                                    date(utc_to_local_time(
                                        point.leave_date_time.replace(tzinfo=None),
                                        user.wialon_tz
                                    ), 'd.m.Y H:i:s')
                                )

                                row['plan_period'] = '%s - %s' % (
                                    date(utc_to_local_time(
                                        job.date_begin.replace(tzinfo=None),
                                        user.wialon_tz
                                    ), 'd.m.Y H:i:s'),
                                    date(utc_to_local_time(
                                        job.date_end.replace(tzinfo=None),
                                        user.wialon_tz
                                    ), 'd.m.Y H:i:s')
                                )
                                row['route_id'] = job.route_id
                                row['point_name'] = point.title
                                row['point_type'] = get_point_type(point.title)
                                row['car_number'] = get_car_number(job.unit_id, units_dict)
                                row['driver_fio'] = job.driver_fio if job.driver_fio else ''
                                overstatement = round(overstatement / 60.0, 2) \
                                    if overstatement > 1.0 else round(overstatement / 60.0, 4)
                                row['overstatement'] = overstatement

                                report_data.append(row)

                    spaces_total_time /= 60.0
                    if spaces \
                            and standard['space_overstatements_standard'] is not None \
                            and spaces_total_time / standard['space_overstatements_standard'] \
                            > normal_ratio:
                        row = self.get_new_grouping()
                        # период пока не указываем, так как это по всему маршруту
                        row['fact_period'] = '%s - %s' % (
                            date(utc_to_local_time(
                                spaces[0].enter_date_time.replace(tzinfo=None),
                                user.wialon_tz
                            ), 'd.m.Y H:i:s'),
                            date(utc_to_local_time(
                                spaces[-1].leave_date_time.replace(tzinfo=None),
                                user.wialon_tz
                            ), 'd.m.Y H:i:s')
                        )
                        row['plan_period'] = '%s - %s' % (
                            date(utc_to_local_time(
                                job.date_begin.replace(tzinfo=None),
                                user.wialon_tz
                            ), 'd.m.Y H:i:s'),
                            date(utc_to_local_time(
                                job.date_end.replace(tzinfo=None),
                                user.wialon_tz
                            ), 'd.m.Y H:i:s')
                        )
                        row['route_id'] = job.route_id
                        row['point_name'] = 'SPACE'
                        row['point_type'] = '0'
                        row['car_number'] = get_car_number(job.unit_id, units_dict)
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

        for col in range(8):
            worksheet.col(col).width = 5000
        worksheet.col(3).width = 12000

        # header
        worksheet.write_merge(1, 1, 0, 7, 'В процессе реализации')

        return worksheet
