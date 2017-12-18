# -*- coding: utf-8 -*-
from collections import OrderedDict
import datetime

from django.db.models import Prefetch, Q

from base.exceptions import ReportException
from base.utils import get_point_type
from reports import forms
from reports.utils import local_to_utc_time
from reports.views.base import BaseReportView, WIALON_NOT_LOGINED, WIALON_USER_NOT_FOUND
from ura.models import UraJob, StandardJobTemplate, StandardPoint
from users.models import User
from wialon.api import get_routes, get_units


class OverstatementsView(BaseReportView):
    """Отчет о сверхнормативных простоях"""
    form = forms.DrivingStyleForm
    template_name = 'reports/overstatements.html'
    report_name = 'Отчет о сверхнормативных простоях'

    @staticmethod
    def get_new_grouping():
        return {
            'period': '',
            'route_id': '',
            'point_name': '',
            'point_type': '',
            'car_number': '',
            'driver_fio': '',
            'overstatement': ''
        }

    def get_context_data(self, **kwargs):
        kwargs = super(OverstatementsView, self).get_context_data(**kwargs)
        report_data = None
        form = kwargs['form']
        kwargs['today'] = datetime.date.today()
        stats = {
            'total': 0
        }

        if self.request.POST:
            report_data = OrderedDict()

            if form.is_valid():
                sess_id = self.request.session.get('sid')
                if not sess_id:
                    raise ReportException(WIALON_NOT_LOGINED)

                user = User.objects.filter(is_active=True) \
                    .filter(wialon_username=self.request.session.get('user')).first()
                if not user:
                    raise ReportException(WIALON_USER_NOT_FOUND)

                dt_from = local_to_utc_time(form.cleaned_data['dt_from'], user.wialon_tz)
                dt_to = local_to_utc_time(form.cleaned_data['dt_to'], user.wialon_tz)

                routes = {
                    x['id']: x for x in get_routes(sess_id=sess_id, user=user, with_points=True)
                }
                units_dict = {x['id']: x for x in get_units(user=user, sess_id=sess_id)}

                standard_job_templates = StandardJobTemplate.objects\
                    .filter(wialon_id__in=[str(x) for x in routes.keys()])\
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
                        'space_overstatements_standard': x.space_overstatements_standard,
                        'points': {
                            p.title: {
                                'total_time_standard': p.total_time_standard,
                                'parking_time_standard': p.parking_time_standard
                            } for p in x.points_cache
                        }
                    } for x in standard_job_templates
                    if x.space_overstatements_standard is not None or x.points_cache
                }

                jobs = UraJob.objects.filter(
                    date_begin__gte=dt_from,
                    date_end__lte=dt_to,
                    route_id__in=list(routes.keys())
                ).prefetch_related('points')

                def get_car_number(unit_id, _units_dict):
                    return _units_dict.get(int(unit_id), {}).get('number', '<%s>' % unit_id)

                spaces_total_time = .0
                spaces = []

                if jobs:
                    report_data = []

                for job in jobs:
                    standard = standards.get(int(job.route_id))
                    if not standard:
                        continue

                    for point in job.points.order_by('id'):

                        if point.title.lower() == 'space':
                            spaces.append(point)
                            spaces_total_time += point.total_time

                        else:
                            point_standard = standard.get(point.title)
                            if not point_standard:
                                continue

                            overstatement = .0
                            if point_standard['total_time_standard'] is not None\
                                    and point.total_time / 60.0 > \
                                    point_standard['total_time_standard']:
                                overstatement += (point.total_time / 60.0)\
                                                 - point_standard['total_time_standard']

                            if point_standard['parking_time_standard'] is not None\
                                    and point.parking_time / 60.0 > \
                                    point_standard['parking_time_standard']:
                                overstatement += (point.parking_time / 60.0)\
                                                 - point_standard['parking_time_standard']

                            if overstatement > .0:
                                stats['total'] += overstatement
                                row = self.get_new_grouping()
                                row['period'] = '%s - %s'
                                row['route_id'] = job.route_id
                                row['point_name'] = point.title
                                row['point_type'] = get_point_type(point.title)
                                row['car_number'] = get_car_number(job.unit_id, units_dict)
                                row['driver_fio'] = job.driver_fio if job.driver_fio else ''
                                row['overstatement'] = round(overstatement / 60.0, 2)

                                report_data.append(row)

                    spaces_total_time /= 60.0
                    if standard['space_overstatements_standard'] is not None \
                            and spaces_total_time > standard['space_overstatements_standard']:
                        row = self.get_new_grouping()
                        # период пока не указываем, так как это по всему маршруту
                        row['period'] = ''
                        row['route_id'] = job.route_id
                        row['point_name'] = 'SPACE'
                        row['point_type'] = '0'
                        row['car_number'] = get_car_number(job.unit_id, units_dict)
                        row['driver_fio'] = job.driver_fio if job.driver_fio else ''
                        row['overstatement'] = round((
                            spaces_total_time - standard['space_overstatements_standard']
                        ) / 60.0, 2)

                        report_data.append(row)
                        stats['total'] += row['overstatement']

        kwargs.update(
            stats=stats,
            report_data=report_data
        )

        return kwargs
