# -*- coding: utf-8 -*-
from collections import OrderedDict
import datetime

from django.utils.timezone import utc

from base.exceptions import ReportException
from reports import forms
from reports.utils import local_to_utc_time, utc_to_local_time
from reports.views.base import BaseReportView, WIALON_NOT_LOGINED, WIALON_USER_NOT_FOUND
from ura.models import Job
from users.models import User
from wialon.api import get_routes, get_units


class InvalidJobStartEndView(BaseReportView):
    """Отчет о несвоевременном начале и окончании выполнения задания"""
    form = forms.InvalidJobStartEndForm
    template_name = 'reports/invalid_job_start_end.html'
    report_name = 'Отчет о несвоевременном начале и окончании выполнения задания'

    def get_default_form(self):
        data = self.request.POST if self.request.method == 'POST' else {
            'dt_from': datetime.datetime.now().replace(hour=0, minute=0, second=0, tzinfo=utc),
            'dt_to': datetime.datetime.now().replace(hour=23, minute=59, second=59, tzinfo=utc)
        }
        return self.form(data)

    @staticmethod
    def get_new_start_grouping():
        return {
            'car_number': '',
            'driver_fio': '',
            'job_date_start': '',
            'route_id': '',
            'route_title': '',
            'route_fact_start': '',
            'fact_start': ''
        }

    @staticmethod
    def get_new_end_grouping():
        return {
            'car_number': '',
            'driver_fio': '',
            'job_date_end': '',
            'route_id': '',
            'route_title': '',
            'fact_end': '',
            'delta': ''
        }

    def get_context_data(self, **kwargs):
        kwargs = super(InvalidJobStartEndView, self).get_context_data(**kwargs)
        report_data = None
        form = kwargs['form']
        stats = {}
        kwargs['today'] = datetime.date.today()

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
                dt_to = local_to_utc_time(
                    form.cleaned_data['dt_to'].replace(second=59), user.wialon_tz
                )

                routes = {
                    x['id']: x for x in get_routes(sess_id=sess_id, user=user, with_points=True)
                }
                units_dict = {x['id']: x for x in get_units(user=user, sess_id=sess_id)}

                jobs = Job.objects.filter(
                    date_begin__gte=dt_from,
                    date_end__lte=dt_to,
                    route_id__in=list(routes.keys())
                ).prefetch_related('points')

                if jobs:
                    report_data = dict(
                        start=[],
                        end=[]
                    )

                def get_car_number(unit_id, _units_dict):
                    return _units_dict.get(int(unit_id), {}).get('number', '<%s>' % unit_id)

                for job in jobs:
                    route = routes.get(int(job.route_id))
                    route_points = route['points']
                    has_base = len(
                        list(filter(lambda x: 'база' in x['name'].lower(), route_points))
                    ) > 0

                    points = list(job.points.order_by('id'))

                    if not points:
                        # кэша нет, пропускаем
                        continue

                    start_point = points[0]
                    start_point_name = start_point.title.lower().strip()

                    if (has_base and 'база' not in start_point_name)\
                            or (
                                not has_base
                                and 'погрузк' not in start_point_name
                                and 'база' not in start_point_name
                            ):
                        row = self.get_new_start_grouping()

                        row['car_number'] = get_car_number(job.unit_id, units_dict)
                        row['driver_fio'] = job.driver_fio.strip()
                        row['job_date_start'] = utc_to_local_time(
                            job.date_begin.replace(tzinfo=None), user.wialon_tz
                        )
                        row['route_id'] = str(job.route_id)
                        row['route_title'] = routes.get(int(job.route_id), {}).get('name', '')
                        row['route_fact_start'] = start_point.title

                        if start_point_name == 'space':
                            row['fact_start'] = '%s, %s' % (start_point.lat, start_point.lng)

                        report_data['start'].append(row)

                    if len(points) <= 1:
                        continue

                    end_point = points[-1]
                    if not end_point.enter_date_time:
                        continue

                    delta = (job.date_end - end_point.enter_date_time).seconds / 60.0
                    if delta < 30:
                        continue

                    row = self.get_new_end_grouping()
                    row['car_number'] = get_car_number(job.unit_id, units_dict)
                    row['driver_fio'] = job.driver_fio.strip()
                    row['job_date_end'] = utc_to_local_time(
                        job.date_end.replace(tzinfo=None), user.wialon_tz
                    )
                    row['route_id'] = str(job.route_id)
                    row['route_title'] = routes.get(int(job.route_id), {}).get('name', '')
                    row['fact_end'] = utc_to_local_time(
                        end_point.enter_date_time.replace(tzinfo=None), user.wialon_tz
                    )
                    row['delta'] = round(delta / 60.0, 2)

                    report_data['end'].append(row)

        kwargs.update(
            stats=stats,
            report_data=report_data
        )

        return kwargs
