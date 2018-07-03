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
from ura.utils import is_fixed_route
from users.models import User
from wialon.api import get_routes


class FinishedJobsView(BaseReportView):
    """Отчет по актуальности шаблонов заданий"""
    form_class = forms.FinishedJobsForm
    template_name = 'reports/finished_jobs.html'
    report_name = 'Отчет по актуальности шаблонов заданий'
    xls_heading_merge = 4

    def get_default_form(self):
        data = self.request.POST if self.request.method == 'POST' else {
            'dt_from': datetime.datetime.now()
            .replace(day=1, hour=0, minute=0, second=0, tzinfo=utc),
            'dt_to': datetime.datetime.now().replace(hour=23, minute=59, second=59, tzinfo=utc),
            'non_actual_param': 20
        }
        return self.form_class(data)

    @staticmethod
    def get_new_grouping(key=''):
        return {
            'key': key,
            'name': '',
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

                dt_from = local_to_utc_time(form.cleaned_data['dt_from'], user.timezone)
                dt_to = local_to_utc_time(
                    form.cleaned_data['dt_to'].replace(second=59), user.timezone
                )

                routes_list = get_routes(sess_id=sess_id, user=user, with_points=True)
                routes_dict = {
                    x['id']: x for x in routes_list if not is_fixed_route(x['name'])
                }
                all_routes_dict = {x['id']: x for x in routes_list}
                used_routes = set()

                stats['total'] = len(routes_dict)

                ura_user = user.ura_user if user.ura_user_id else user
                jobs = Job.objects\
                    .filter(
                        user=ura_user,
                        date_begin__gte=dt_from,
                        date_end__lte=dt_to,
                        route_id__in=list(routes_dict.keys())
                    )\
                    .prefetch_related('points').order_by('date_begin', 'date_end')

                for job in jobs:
                    route = routes_dict.get(int(job.route_id))
                    if not route:
                        possible_route_name = all_routes_dict.get(int(job.route_id), {})\
                            .get('name', '')
                        if not is_fixed_route(possible_route_name):
                            print(
                                'Route not found (job_id: %s, route name: %s)' % (
                                    job.pk, possible_route_name
                                )
                            )
                        continue

                    key = int(job.route_id)
                    used_routes.add(key)
                    if key not in report_data:
                        report_data[key] = self.get_new_grouping()
                        report_data[key]['key'] = key
                        report_data[key]['name'] = all_routes_dict.get(key, {}).get('name', '')

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
                report_data = OrderedDict(
                    (x[0], x[1])
                    for x in report_data.items()
                    if x[1]['ratio'] < 100 - form.cleaned_data['non_actual_param']
                )

                # добавим те, которые вообще не использовались:
                unused_routes = [x for x in routes_dict.values() if x['id'] not in used_routes]
                for unused_route in unused_routes:
                    key = unused_route['id']
                    report_data[key] = self.get_new_grouping(key)
                    report_data[key]['name'] = all_routes_dict.get(key, {}).get('name', '')

        kwargs.update(
            stats=stats,
            report_data=report_data
        )

        return kwargs

    def write_xls_data(self, worksheet, context):
        worksheet = super(FinishedJobsView, self).write_xls_data(worksheet, context)

        for col in range(5):
            worksheet.col(col).width = 5000
        worksheet.col(1).width = 12000

        # header
        worksheet.write_merge(
            1, 1, 0, 4, 'За период: %s - %s' % (
                date_format(context['cleaned_data']['dt_from'], 'd.m.Y H:i'),
                date_format(context['cleaned_data']['dt_to'], 'd.m.Y H:i')
            )
        )

        worksheet.write_merge(
            2, 2, 0, 1, 'ФИО ответственного за корректировку:',
            style=self.styles['left_center_style']
        )

        worksheet.write_merge(2, 2, 2, 4, '', style=self.styles['bottom_border_style'])

        worksheet.write_merge(
            3, 3, 0, 4, 'Всего шаблонов заданий в базе ССМТ: %s' % context['stats']['total'],
            style=self.styles['right_center_style']
        )

        worksheet.write_merge(
            4, 4, 0, 4, 'Из них неактуальных заданий: %s' % context['stats']['non_actual'],
            style=self.styles['right_center_style']
        )

        # head
        worksheet.write_merge(
            5, 6, 0, 0, ' № шаблона задания\nиз ССМТ', style=self.styles['border_center_style']
        )
        worksheet.write_merge(
            5, 6, 1, 1, ' Наименование шаблона задания', style=self.styles['border_center_style']
        )
        worksheet.write_merge(
            5, 5, 2, 3, ' Кол-во путевых листов', style=self.styles['border_center_style']
        )
        worksheet.write(6, 2, ' Заявлено', style=self.styles['border_center_style'])
        worksheet.write(6, 3, ' Исполнялось*', style=self.styles['border_center_style'])
        worksheet.write_merge(
            5, 6, 4, 4, ' Актуальность, %', style=self.styles['border_center_style']
        )

        for i in range(5):
            worksheet.write(7, i, str(i + 1), style=self.styles['border_center_style'])

        for i in range(1, 8):
            worksheet.row(i).height = REPORT_ROW_HEIGHT

        # body
        i = 8
        for row in context['report_data'].values():
            worksheet.write(i, 0, row['key'], style=self.styles['border_left_style'])
            worksheet.write(i, 1, row['name'], style=self.styles['border_left_style'])
            worksheet.write(i, 2, row['plan'], style=self.styles['border_right_style'])
            worksheet.write(i, 3, row['finished'], style=self.styles['border_right_style'])
            worksheet.write(i, 4, row['ratio'], style=self.styles['border_right_style'])
            worksheet.row(i).height = REPORT_ROW_HEIGHT
            i += 1

        worksheet.write_merge(
            i + 1, i + 1, 0, 4,
            '''
* Исполненое задание - по факту работы транспорта в рамках одного путевого листа было
зафиксировано посещение заданных заданием геозон, хотя бы однократно.
Условие неактуальности шаблона задания: более %s%% неисполненных заданий
''' %
            context['cleaned_data'].get('non_actual_param', 20),
            style=self.styles['left_center_style']
        )
        worksheet.row(i + 1).height = 520 * 2

        return worksheet
