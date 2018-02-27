# -*- coding: utf-8 -*-
from collections import OrderedDict
import datetime

from base.exceptions import ReportException
from reports import forms
from reports.utils import local_to_utc_time
from reports.views.base import BaseReportView, WIALON_NOT_LOGINED, WIALON_USER_NOT_FOUND
from ura.models import Job
from users.models import User
from wialon.api import get_routes


class FinishedJobsView(BaseReportView):
    """Отчет по актуальности шаблонов заданий"""
    form = forms.DrivingStyleForm
    template_name = 'reports/finished_jobs.html'
    report_name = 'Отчет по актуальности шаблонов заданий'

    @staticmethod
    def get_new_grouping():
        return {
            'key': '',
            'plan': 0,
            'finished': 0,
            'ratio': .0
        }

    def get_context_data(self, **kwargs):
        kwargs = super(FinishedJobsView, self).get_context_data(**kwargs)
        report_data = None
        form = kwargs['form']
        kwargs['today'] = datetime.date.today()
        stats = {
            'total': 0,
            'non_actual': 0
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

                jobs = Job.objects\
                    .filter(
                        date_begin__gte=dt_from,
                        date_end__lte=dt_to,
                        route_id__in=list(routes.keys())
                    )\
                    .prefetch_related('points')

                stats['total'] = len(jobs)

                for job in jobs:
                    key = job.route_id

                    if key not in report_data:
                        report_data[key] = self.get_new_grouping()
                        report_data[key]['key'] = key

                    report_data[key]['plan'] += 1

                    route = routes.get(int(job.route_id))
                    route_points = {p['name'] for p in route['points']}
                    points = list(
                        map(
                            lambda x: x.title,
                            filter(lambda x: x.title != 'SPACE', job.points.all())
                        )
                    )
                    remaining_route_points = [x for x in route_points if x not in points]

                    if remaining_route_points:
                        stats['non_actual'] += 1
                    else:
                        report_data[key]['finished'] += 1

                for v in report_data.values():
                    v['ratio'] = round((v['finished'] / v['plan']) * 100, 2)

                # убираем полностью завершенные
                report_data = {x[0]: x[1] for x in report_data.items() if x[1]['ratio'] < 100}

        kwargs.update(
            stats=stats,
            report_data=report_data
        )

        return kwargs
