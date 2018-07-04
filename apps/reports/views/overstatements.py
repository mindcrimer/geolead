import datetime

from django.utils.formats import date_format

from django.db.models import Prefetch, Q
from django.utils.timezone import utc

from base.exceptions import ReportException
from base.utils import get_point_type
from reports import forms, DEFAULT_OVERSTATEMENT_NORMAL_PERCENTAGE
from reports.jinjaglobals import date
from reports.utils import local_to_utc_time, utc_to_local_time
from reports.views.base import BaseReportView, WIALON_NOT_LOGINED, WIALON_USER_NOT_FOUND, \
    REPORT_ROW_HEIGHT
from ura.models import Job, StandardJobTemplate, StandardPoint, JobPoint
from users.models import User
from wialon.api import get_routes, get_units


class OverstatementsView(BaseReportView):
    """Отчет о сверхнормативных простоях"""
    form_class = forms.OverstatementsForm
    template_name = 'reports/overstatements.html'
    report_name = 'Отчет о сверхнормативных простоях'
    xls_heading_merge = 7

    def get_default_form(self):
        data = self.request.POST if self.request.method == 'POST' else {
            'dt_from': datetime.datetime.now().replace(hour=0, minute=0, second=0, tzinfo=utc),
            'dt_to': datetime.datetime.now().replace(hour=23, minute=59, second=59, tzinfo=utc),
            'overstatement_param': DEFAULT_OVERSTATEMENT_NORMAL_PERCENTAGE
        }
        return self.form_class(data)

    def get_default_context_data(self, **kwargs):
        context = super(OverstatementsView, self).get_default_context_data(**kwargs)
        context.update({
            'overstatement_param': DEFAULT_OVERSTATEMENT_NORMAL_PERCENTAGE
        })
        return context

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
        kwargs = super(OverstatementsView, self).get_context_data(**kwargs)
        report_data = None
        form = kwargs['form']
        kwargs['today'] = datetime.date.today()
        stats = {
            'total': 0
        }

        if self.request.POST:
            report_data = []

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

                routes = {
                    x['id']: x for x in get_routes(sess_id, with_points=True)
                }
                units_dict = {x['id']: x for x in get_units(sess_id)}

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
                jobs = Job.objects \
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
                            if point_standard['total_time_standard'] is not None\
                                    and total_time / point_standard['total_time_standard'] \
                                    > normal_ratio:
                                overstatement += total_time - point_standard['total_time_standard']

                            parking_time = point.parking_time / 60.0
                            if point_standard['parking_time_standard'] is not None\
                                    and parking_time / point_standard['parking_time_standard'] \
                                    > normal_ratio:
                                overstatement += parking_time \
                                    - point_standard['parking_time_standard']

                            if overstatement > .0:
                                stats['total'] += overstatement / 60.0
                                row = self.get_new_grouping()
                                row['fact_period'] = '%s - %s' % (
                                    date(utc_to_local_time(
                                        point.enter_date_time.replace(tzinfo=None),
                                        user.timezone
                                    ), 'd.m.Y H:i:s'),
                                    date(utc_to_local_time(
                                        point.leave_date_time.replace(tzinfo=None),
                                        user.timezone
                                    ), 'd.m.Y H:i:s')
                                )

                                row['plan_period'] = '%s - %s' % (
                                    date(utc_to_local_time(
                                        job.date_begin.replace(tzinfo=None),
                                        user.timezone
                                    ), 'd.m.Y H:i:s'),
                                    date(utc_to_local_time(
                                        job.date_end.replace(tzinfo=None),
                                        user.timezone
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
                                user.timezone
                            ), 'd.m.Y H:i:s'),
                            date(utc_to_local_time(
                                spaces[-1].leave_date_time.replace(tzinfo=None),
                                user.timezone
                            ), 'd.m.Y H:i:s')
                        )
                        row['plan_period'] = '%s - %s' % (
                            date(utc_to_local_time(
                                job.date_begin.replace(tzinfo=None),
                                user.timezone
                            ), 'd.m.Y H:i:s'),
                            date(utc_to_local_time(
                                job.date_end.replace(tzinfo=None),
                                user.timezone
                            ), 'd.m.Y H:i:s')
                        )
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

            report_data = sorted(report_data, key=lambda k: k['fact_period'])

        if stats['total']:
            stats['total'] = round(stats['total'], 2)

        kwargs.update(
            stats=stats,
            report_data=report_data
        )

        return kwargs

    def write_xls_data(self, worksheet, context):
        worksheet = super(OverstatementsView, self).write_xls_data(worksheet, context)

        for col in range(8):
            worksheet.col(col).width = 5000
        worksheet.col(3).width = 12000

        # header
        worksheet.write_merge(
            1, 1, 0, 7, 'За период: %s - %s' % (
                date_format(context['cleaned_data']['dt_from'], 'd.m.Y H:i'),
                date_format(context['cleaned_data']['dt_to'], 'd.m.Y H:i')
            )
        )

        worksheet.write_merge(
            2, 2, 0, 7, 'Итого часов перепростоя: %s' % context['stats']['total'],
            style=self.styles['right_center_style']
        )

        worksheet.write_merge(
            3, 3, 0, 7, 'Список сверхнормативных простоев на дату',
            style=self.styles['right_center_style']
        )

        # head
        worksheet.write(
            4, 0, ' Время пребывания в геозоне с__по__', style=self.styles['border_center_style']
        )
        worksheet.write(
            4, 1, ' Плановый график\nработы водителя\nс__по__',
            style=self.styles['border_center_style']
        )
        worksheet.write(
            4, 2, ' № шаблона задания', style=self.styles['border_center_style']
        )
        worksheet.write(
            4, 3, ' Наименование геозоны', style=self.styles['border_center_style']
        )
        worksheet.write(
            4, 4, ' Тип геозоны', style=self.styles['border_center_style']
        )
        worksheet.write(
            4, 5, ' гос № ТС', style=self.styles['border_center_style']
        )
        worksheet.write(
            4, 6, ' ФИО водителя', style=self.styles['border_center_style']
        )
        worksheet.write(
            4, 7, ' *Перепростой\n/перенахождение, ч.', style=self.styles['border_center_style']
        )

        for i in range(1, 5):
            worksheet.row(i).height = REPORT_ROW_HEIGHT
        worksheet.row(4).height = 780

        # body
        i = 5
        for row in context['report_data']:
            worksheet.write(i, 0, row['fact_period'], style=self.styles['border_left_style'])
            worksheet.write(i, 1, row['plan_period'], style=self.styles['border_left_style'])
            worksheet.write(i, 2, row['route_id'], style=self.styles['border_left_style'])
            worksheet.write(i, 3, row['point_name'], style=self.styles['border_left_style'])
            worksheet.write(i, 4, row['point_type'], style=self.styles['border_right_style'])
            worksheet.write(i, 5, row['car_number'], style=self.styles['border_left_style'])
            worksheet.write(i, 6, row['driver_fio'], style=self.styles['border_left_style'])
            worksheet.write(i, 7, row['overstatement'], style=self.styles['border_right_style'])
            worksheet.row(i).height = 520
            i += 1

        worksheet.write_merge(
            i, i, 0, 7,
            '*В случае превышения фактического простоя над нормативным более чем на %s%%' %
            context['cleaned_data'].get('overstatement_param', 5),
            style=self.styles['left_center_style']
        )
        worksheet.row(i + 1).height = 520

        return worksheet
