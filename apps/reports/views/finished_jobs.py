# -*- coding: utf-8 -*-
from collections import OrderedDict
import datetime

from django.utils.timezone import utc

from base.exceptions import ReportException
from reports import forms
from reports.utils import local_to_utc_time
from reports.views.base import BaseReportView, WIALON_NOT_LOGINED, WIALON_USER_NOT_FOUND, \
    REPORT_ROW_HEIGHT
from snippets.jinjaglobals import date as date_format
from ura.models import Job
from users.models import User
from wialon.api import get_routes


class FinishedJobsView(BaseReportView):
    """Отчет по актуальности шаблонов заданий"""
    form_class = forms.FinishedJobsForm
    template_name = 'reports/finished_jobs.html'
    report_name = 'Отчет по актуальности шаблонов заданий'
    can_download = True

    def get_default_form(self):
        data = self.request.POST if self.request.method == 'POST' else {
            'dt_from': datetime.datetime.now()
            .replace(day=1, hour=0, minute=0, second=0, tzinfo=utc),
            'dt_to': datetime.datetime.now().replace(hour=23, minute=59, second=59, tzinfo=utc),
            'non_actual_param': 20
        }
        return self.form_class(data)

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
                dt_to = local_to_utc_time(
                    form.cleaned_data['dt_to'].replace(second=59), user.wialon_tz
                )

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

                for job in jobs:
                    route = routes.get(int(job.route_id))
                    if not route or 'фиксирован' in route['name'].lower():
                        continue

                    stats['total'] += 1

                    key = job.route_id
                    if key not in report_data:
                        report_data[key] = self.get_new_grouping()
                        report_data[key]['key'] = key

                    report_data[key]['plan'] += 1

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
                report_data = {
                    x[0]: x[1]
                    for x in report_data.items()
                    if x[1]['ratio'] < 100 - form.cleaned_data['non_actual_param']
                }

        kwargs.update(
            stats=stats,
            report_data=report_data
        )

        return kwargs

    def write_xls_data(self, worksheet, context):
        worksheet = super(FinishedJobsView, self).write_xls_data(worksheet, context)

        for col in range(4):
            worksheet.col(col).width = 5000

        # header
        worksheet.write_merge(
            1, 1, 0, 3, 'За период: %s - %s' % (
                date_format(context['cleaned_data']['dt_from'], 'd.m.Y H:i'),
                date_format(context['cleaned_data']['dt_to'], 'd.m.Y H:i')
            )
        )

        worksheet.write_merge(
            2, 2, 0, 1, 'ФИО ответственного за корректировку:',
            style=self.styles['left_center_style']
        )

        worksheet.write_merge(2, 2, 2, 3, '', style=self.styles['bottom_border_style'])

        worksheet.write_merge(
            3, 3, 0, 3, 'Всего шаблонов заданий в базе ССМТ: %s' % context['stats']['total'],
            style=self.styles['right_center_style']
        )

        worksheet.write_merge(
            4, 4, 0, 3, 'Из них неактуальных заданий: %s' % context['stats']['non_actual'],
            style=self.styles['right_center_style']
        )

        # head
        worksheet.write_merge(
            5, 6, 0, 0, ' № шаблона задания\nиз ССМТ', style=self.styles['border_left_style']
        )
        worksheet.write_merge(
            5, 5, 1, 2, ' Кол-во путевых листов', style=self.styles['border_left_style']
        )
        worksheet.write_merge(
            5, 6, 3, 3, ' Актуальность, %', style=self.styles['border_left_style']
        )
        worksheet.write(6, 1, ' Заявлено', style=self.styles['border_left_style'])
        worksheet.write(6, 2, ' Исполнялось*', style=self.styles['border_left_style'])

        for i in range(1, 7):
            worksheet.row(i).height = REPORT_ROW_HEIGHT

        # body
        for i, row in enumerate(context['report_data'].values(), 7):
            worksheet.write(i, 0, row['key'], style=self.styles['border_left_style'])
            worksheet.write(i, 1, row['plan'], style=self.styles['border_right_style'])
            worksheet.write(i, 2, row['finished'], style=self.styles['border_right_style'])
            worksheet.write(i, 3, row['ratio'], style=self.styles['border_right_style'])
            worksheet.row(i).height = REPORT_ROW_HEIGHT

        return worksheet
