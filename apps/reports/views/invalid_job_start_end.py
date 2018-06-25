from collections import OrderedDict
import datetime

from django.utils.formats import date_format

from django.utils.timezone import utc

from base.exceptions import ReportException
from base.utils import get_point_type
from reports import forms
from reports.utils import local_to_utc_time, utc_to_local_time
from reports.views.base import BaseReportView, WIALON_NOT_LOGINED, WIALON_USER_NOT_FOUND, \
    REPORT_ROW_HEIGHT
from ura.models import Job
from ura.utils import is_fixed_route
from users.models import User
from wialon.api import get_routes, get_units


class InvalidJobStartEndView(BaseReportView):
    """Отчет о несвоевременном начале и окончании выполнения задания"""
    form_class = forms.InvalidJobStartEndForm
    template_name = 'reports/invalid_job_start_end.html'
    report_name = 'Отчет о несвоевременном начале и окончании выполнения задания'
    xls_heading_merge = 8

    def get_default_form(self):
        data = self.request.POST if self.request.method == 'POST' else {
            'dt_from': datetime.datetime.now().replace(hour=0, minute=0, second=0, tzinfo=utc),
            'dt_to': datetime.datetime.now().replace(hour=23, minute=59, second=59, tzinfo=utc),
            'job_end_timeout': 30
        }
        return self.form_class(data)

    @staticmethod
    def get_new_start_grouping():
        return {
            'car_number': '',
            'driver_fio': '',
            'job_date_start': '',
            'point_type': '',
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
            'point_title': '',
            'point_type': '',
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
            if form.is_valid():
                report_data = OrderedDict()
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

                routes_dict = {
                    x['id']: x for x in get_routes(sess_id=sess_id, user=user, with_points=True)
                }
                units_dict = {x['id']: x for x in get_units(user=user, sess_id=sess_id)}

                ura_user = user.ura_user if user.ura_user_id else user
                jobs = Job.objects.filter(
                    user=ura_user,
                    date_begin__gte=dt_from,
                    date_end__lte=dt_to,
                    route_id__in=list(routes_dict.keys())
                ).prefetch_related('points')

                if jobs:
                    report_data = dict(
                        start=[],
                        end=[]
                    )

                def get_car_number(unit_id, _units_dict):
                    return _units_dict.get(int(unit_id), {}).get('number', '')

                for job in jobs:
                    route = routes_dict.get(int(job.route_id))

                    if not route:
                        print('No route found! job_id=%s' % job.pk)
                        continue

                    elif not form.cleaned_data.get('include_fixed', False) \
                            and is_fixed_route(route['name']):
                        print(
                            'Fixed route was skipped. job_id=%s, route=%s' % (
                                job.pk, route['name']
                            )
                        )
                        continue

                    route_points = route['points']
                    has_base = len(
                        list(filter(lambda x: 'база' in x['name'].lower(), route_points))
                    ) > 0

                    points = list(job.points.order_by('id'))

                    if not points:
                        # кэша нет, пропускаем
                        print('No job moving cache! job_id=%s' % job.pk)
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
                        row['point_type'] = get_point_type(start_point.title)
                        row['route_id'] = str(job.route_id)
                        row['route_title'] = routes_dict.get(int(job.route_id), {}).get('name', '')
                        row['route_fact_start'] = start_point.title

                        if start_point_name == 'space':
                            row['fact_start'] = '%s, %s' % (start_point.lat, start_point.lng)

                        report_data['start'].append(row)

                    if len(points) <= 1:
                        continue

                    end_point = points[-1]
                    if not end_point.enter_date_time:
                        continue

                    delta = (job.date_end - end_point.enter_date_time).total_seconds() / 60.0
                    if delta < form.cleaned_data.get('job_end_timeout', 30.0):
                        continue

                    row = self.get_new_end_grouping()
                    row['car_number'] = get_car_number(job.unit_id, units_dict)
                    row['driver_fio'] = job.driver_fio.strip()
                    row['job_date_end'] = utc_to_local_time(
                        job.date_end.replace(tzinfo=None), user.wialon_tz
                    )
                    row['point_type'] = get_point_type(end_point.title)
                    row['point_title'] = end_point.title
                    row['route_id'] = str(job.route_id)
                    row['route_title'] = routes_dict.get(int(job.route_id), {}).get('name', '')
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

    def write_xls_data(self, worksheet, context):
        worksheet = super(InvalidJobStartEndView, self).write_xls_data(worksheet, context)

        for col in range(9):
            worksheet.col(col).width = 5000
        worksheet.col(0).width = 4000
        worksheet.col(2).width = 6000
        worksheet.col(3).width = 3300
        worksheet.col(4).width = 10000
        worksheet.col(5).width = 10000

        # header
        worksheet.write_merge(
            1, 1, 0, 9, 'За период: %s - %s' % (
                date_format(context['cleaned_data']['dt_from'], 'd.m.Y H:i'),
                date_format(context['cleaned_data']['dt_to'], 'd.m.Y H:i')
            )
        )

        worksheet.write_merge(
            2, 2, 0, 7, 'Список случаев несоответствий выездов*',
            style=self.styles['right_center_style']
        )

        # head
        worksheet.write(
            3, 0, ' Гос № ТС', style=self.styles['border_center_style']
        )
        worksheet.write(
            3, 1, ' ФИО водителя', style=self.styles['border_center_style']
        )
        worksheet.write(
            3, 2, ' Время начала смены\nиз путевого листа',
            style=self.styles['border_center_style']
        )
        worksheet.write(
            3, 3, ' № шаблона\nзадания', style=self.styles['border_center_style']
        )
        worksheet.write(
            3, 4, ' Название шаблона задания', style=self.styles['border_center_style']
        )
        worksheet.write(
            3, 5, ' Фактическое место/геозона\n(в рамках шаблона задания) на начало смены',
            style=self.styles['border_center_style']
        )
        worksheet.write(
            3, 6, ' Фактическое место/геозона на начало смены',
            style=self.styles['border_center_style']
        )
        worksheet.write(
            3, 7, ' Тип фактического места/геозоны\nна начало смены',
            style=self.styles['border_center_style']
        )

        for i in range(8):
            worksheet.write(4, i, str(i + 1), style=self.styles['border_center_style'])

        for i in range(1, 5):
            worksheet.row(i).height = REPORT_ROW_HEIGHT
        worksheet.row(3).height = 780

        # body
        i = 5
        for row in context['report_data'].get('start'):
            worksheet.write(i, 0, row['car_number'], style=self.styles['border_left_style'])
            worksheet.write(i, 1, row['driver_fio'], style=self.styles['border_left_style'])
            worksheet.write(
                i, 2, date_format(row['job_date_start'], 'Y-m-d H:i:s'),
                style=self.styles['border_left_style']
            )
            worksheet.write(i, 3, row['route_id'], style=self.styles['border_left_style'])
            worksheet.write(i, 4, row['route_title'], style=self.styles['border_left_style'])
            worksheet.write(i, 5, row['route_fact_start'], style=self.styles['border_left_style'])
            worksheet.write(i, 6, row['fact_start'], style=self.styles['border_left_style'])
            worksheet.write(i, 7, row['point_type'], style=self.styles['border_right_style'])
            worksheet.row(i).height = 520
            i += 1

        # header
        worksheet.write_merge(
            i, i, 0, 8, '',
            style=self.styles['left_center_style']
        )
        i += 1
        worksheet.write_merge(
            i, i, 0, 8, 'Список случаев несоответствий заездов',
            style=self.styles['right_center_style']
        )

        # head
        i += 1
        worksheet.write(
            i, 0, ' Гос № ТС', style=self.styles['border_center_style']
        )
        worksheet.write(
            i, 1, ' ФИО водителя', style=self.styles['border_center_style']
        )
        worksheet.write(
            i, 2, ' Время окончания смены\nиз путевого листа',
            style=self.styles['border_center_style']
        )
        worksheet.write(
            i, 3, ' № шаблона\nзадания', style=self.styles['border_center_style']
        )
        worksheet.write(
            i, 4, ' Название шаблона задания', style=self.styles['border_center_style']
        )
        worksheet.write(
            i, 5, ' Фактическое место/геозона\nприбытия', style=self.styles['border_center_style']
        )
        worksheet.write(
            i, 6, ' Тип фактического\nместа/геозоны прибытия',
            style=self.styles['border_center_style']
        )
        worksheet.write(
            i, 7, ' Время фактического\nприбытия', style=self.styles['border_center_style']
        )
        worksheet.write(
            i, 8, ' **Отклонение, ч', style=self.styles['border_center_style']
        )
        worksheet.row(i).height = 780

        i += 1
        for l in range(9):
            worksheet.write(i, l, str(l + 1), style=self.styles['border_center_style'])
        worksheet.row(i).height = REPORT_ROW_HEIGHT

        # body
        i += 1
        for row in context['report_data'].get('end'):
            worksheet.write(i, 0, row['car_number'], style=self.styles['border_left_style'])
            worksheet.write(i, 1, row['driver_fio'], style=self.styles['border_left_style'])
            worksheet.write(
                i, 2, date_format(row['job_date_end'], 'Y-m-d H:i:s'),
                style=self.styles['border_left_style']
            )
            worksheet.write(i, 3, row['route_id'], style=self.styles['border_left_style'])
            worksheet.write(i, 4, row['route_title'], style=self.styles['border_left_style'])
            worksheet.write(i, 5, row['point_title'], style=self.styles['border_left_style'])
            worksheet.write(i, 6, row['point_type'], style=self.styles['border_right_style'])
            worksheet.write(
                i, 7, date_format(row['fact_end'], 'Y-m-d H:i:s'),
                style=self.styles['border_left_style']
            )
            worksheet.write(i, 8, row['delta'], style=self.styles['border_right_style'])
            worksheet.row(i).height = 520
            i += 1

        worksheet.write_merge(
            i, i, 0, 8,
            '''
* если во время начала смены автомобиль не находился в стартовой точке
(гараже или соответствующем месте) - фиксируется несоответствие выезда;
** более %s мин. от планового завершения смены
            ''' %
            context['cleaned_data'].get('job_end_timeout', 30),
            style=self.styles['left_center_style']
        )
        worksheet.row(i).height = 520 * 3

        return worksheet
