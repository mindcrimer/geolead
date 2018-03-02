# -*- coding: utf-8 -*-
from collections import OrderedDict, defaultdict
import datetime
import time

from django.utils.timezone import utc

from base.exceptions import ReportException
from reports import forms
from reports.utils import parse_wialon_report_datetime, get_wialon_report_template_id, \
    cleanup_and_request_report, exec_report, get_report_rows, local_to_utc_time, utc_to_local_time
from reports.views.base import BaseReportView, WIALON_NOT_LOGINED, WIALON_USER_NOT_FOUND
from ura.models import Job
from users.models import User
from wialon.api import get_units
from wialon.exceptions import WialonException


class DrivingStyleView(BaseReportView):
    """Стиль вождения"""
    form_class = forms.DrivingStyleForm
    template_name = 'reports/driving_style.html'
    report_name = 'Отчет нарушений ПДД и инструкции по эксплуатации техники'
    can_download = True

    def __init__(self, *args, **kwargs):
        super(DrivingStyleView, self).__init__(*args, **kwargs)
        self.form = None

    def get_default_form(self):
        data = self.request.POST if self.request.method == 'POST' else {
            'dt_from': datetime.datetime.now().replace(hour=0, minute=0, second=0, tzinfo=utc),
            'dt_to': datetime.datetime.now().replace(hour=23, minute=59, second=59, tzinfo=utc),
            'normal_rating': 10,
            'bad_rating': 30
        }
        return self.form_class(data)

    @staticmethod
    def get_new_grouping():
        return {
            'unit_name': '',
            'periods': []
        }

    @staticmethod
    def get_new_period(dt_from, dt_to, job=None):
        return {
            'dt_from': dt_from,
            'dt_to': dt_to,
            't_from': int(dt_from.timestamp()),
            't_to': int(dt_to.timestamp()),
            'job': job,
            'total_time': (dt_to - dt_from).total_seconds(),
            'facts': {
                'speed': {
                    'count': 0,
                    'seconds': .0
                },
                'lights': {
                    'count': 0,
                    'seconds': .0
                },
                'belt': {
                    'count': 0,
                    'seconds': .0
                },
                'devices': {
                    'count': 0,
                    'seconds': .0
                }
            },
            'percentage': {
                'speed': .0,
                'lights': .0,
                'belt': .0,
                'devices': .0
            },
            'rating': 100.0,
            'details': []
        }

    @staticmethod
    def parse_time_delta(value):
        delta = datetime.timedelta(seconds=0)
        parts = value.split(' ')
        digits = 0

        for part in parts:

            if part.isdigit():
                digits = int(part)
                continue

            if ':' in part:
                hours, minutes, seconds = [int(x) for x in part.split(':')]
                delta += datetime.timedelta(seconds=((hours * 3600) + (minutes * 60) + seconds))

            elif 'day' in part or 'дн' in part or 'ден' in part:
                delta += datetime.timedelta(days=digits)

            elif 'week' in part or 'недел' in part:
                delta += datetime.timedelta(days=digits * 7)

            elif 'month' in part or 'месяц' in part:
                delta += datetime.timedelta(days=digits * 30)

            elif 'year' in part or 'год' in part or 'лет' in part:
                delta += datetime.timedelta(days=digits * 365)

        return delta

    def get_context_data(self, **kwargs):
        kwargs = super(DrivingStyleView, self).get_context_data(**kwargs)
        report_data = None
        self.form = kwargs['form']
        kwargs['today'] = datetime.date.today()

        if self.request.POST:
            report_data = OrderedDict()

            if self.form.is_valid():
                sess_id = self.request.session.get('sid')
                if not sess_id:
                    raise ReportException(WIALON_NOT_LOGINED)

                user = User.objects.filter(is_active=True) \
                    .filter(wialon_username=self.request.session.get('user')).first()

                if not user:
                    raise ReportException(WIALON_USER_NOT_FOUND)

                try:
                    units_list = get_units(sess_id=sess_id, extra_fields=True)
                except WialonException as e:
                    raise ReportException(str(e))

                units_dict = OrderedDict((u['id'], u['name']) for u in units_list)

                dt_from_utc = local_to_utc_time(self.form.cleaned_data['dt_from'], user.wialon_tz)
                dt_to_utc = local_to_utc_time(
                    self.form.cleaned_data['dt_to'].replace(second=59), user.wialon_tz
                )

                ura_user = user.ura_user if user.ura_user_id else user
                jobs = Job.objects.filter(
                    user=ura_user, date_begin__lt=dt_to_utc, date_end__gt=dt_from_utc
                ).order_by('date_begin', 'date_end')

                jobs_cache = defaultdict(list)
                for job in jobs:
                    try:
                        jobs_cache[int(job.unit_id)].append(job)
                    except ValueError:
                        pass

                template_id = get_wialon_report_template_id('driving_style_individual', user)

                print('Всего ТС: %s' % len(units_dict))

                i = 0
                for unit_id, unit_name in units_dict.items():
                    i += 1
                    # FIXME
                    if i > 10:
                        break
                    print('%s) %s' % (i, unit_name))

                    if unit_id not in report_data:
                        report_data[unit_id] = self.get_new_grouping()
                    report_row = report_data[unit_id]
                    report_row['unit_name'] = unit_name

                    unit_jobs = jobs_cache.get(unit_id)
                    if not unit_jobs:
                        report_row['periods'].append(self.get_new_period(dt_from_utc, dt_to_utc))
                    else:
                        if unit_jobs[0].date_begin > dt_from_utc:
                            # если начало периода не попадает на смену
                            report_row['periods'].append(
                                self.get_new_period(dt_from_utc, unit_jobs[0].date_begin)
                            )

                        previous_job = None
                        for unit_job in unit_jobs:
                            # если между сменами есть перерыв, то тоже добавляем период
                            if previous_job and unit_job.date_begin > previous_job.date_end:
                                report_row['periods'].append(
                                    self.get_new_period(previous_job.date_end, unit_job.date_begin)
                                )

                            report_row['periods'].append(
                                self.get_new_period(
                                    unit_job.date_begin, unit_job.date_end, unit_job
                                )
                            )

                            previous_job = unit_job

                        if unit_jobs[-1].date_end < dt_to_utc:
                            # если смена закончилась до конца периода
                            report_row['periods'].append(
                                self.get_new_period(unit_jobs[-1].date_end, dt_to_utc)
                            )

                    # получим полный диапазон запроса
                    dt_from = int(time.mktime(report_row['periods'][0]['dt_from'].timetuple()))
                    dt_to = int(time.mktime(report_row['periods'][-1]['dt_to'].timetuple()))

                    cleanup_and_request_report(user, template_id, sess_id=sess_id)
                    r = exec_report(
                        user, template_id, dt_from, dt_to,
                        sess_id=sess_id, object_id=unit_id
                    )

                    wialon_report_rows = []
                    for table_index, table_info in enumerate(r['reportResult']['tables']):

                        if table_info['name'] != 'unit_ecodriving':
                            continue

                        wialon_report_rows = get_report_rows(
                            user,
                            table_index,
                            table_info['rows'],
                            level=1,
                            sess_id=sess_id
                        )

                    for row in wialon_report_rows:
                        detail_data = {
                            'speed': {
                                'count': 0,
                                'seconds': .0
                            },
                            'lights': {
                                'count': 0,
                                'seconds': .0
                            },
                            'belt': {
                                'count': 0,
                                'seconds': .0
                            },
                            'devices': {
                                'count': 0,
                                'seconds': .0
                            },
                            'dt': ''
                        }
                        violation = row['c'][3].lower() if row['c'][3] else ''
                        if 'свет' in violation or 'фар' in violation:
                            viol_key = 'lights'
                        elif 'скорост' in violation or 'превышен' in violation:
                            viol_key = 'speed'
                        elif 'ремн' in violation or 'ремен' in violation:
                            viol_key = 'belt'
                        else:
                            viol_key = ''

                        if viol_key:
                            if detail_data:
                                detail_data['dt'] = parse_wialon_report_datetime(
                                    row['c'][8]['t']
                                    if isinstance(row['c'][8], dict)
                                    else row['c'][8]
                                )

                                for period in report_row['periods']:
                                    if period['t_from'] < row['t2'] and period['t_to'] > row['t1']:
                                        delta = min(row['t2'], period['t_to']) - \
                                                max(row['t1'], period['t_from'])
                                        detail_data[viol_key]['seconds'] = delta
                                        period['details'].append(detail_data)
                                        period['facts'][viol_key]['count'] += 1
                                        period['facts'][viol_key]['seconds'] += delta

                    report_row['periods'] = list(
                        filter(
                            lambda x: len(x['details']) > 0,
                            report_row['periods'])
                    )

                    for period in report_row['periods']:
                        period['dt_from'] = utc_to_local_time(period['dt_from'], user.wialon_tz)
                        period['dt_to'] = utc_to_local_time(period['dt_to'], user.wialon_tz)

                        for viol_key in ('speed', 'lights', 'belt', 'devices'):
                            percentage = period['facts'][viol_key]['seconds'] / \
                                         period['total_time'] * 100
                            period['percentage'][viol_key] = percentage
                            period['rating'] -= percentage

                kwargs.update(
                    report_data=report_data,
                    render_background=self.render_background,
                    enumerate=enumerate
                )

        return kwargs

    def render_background(self, value):
        if value is None:
            return '#FFF'

        if value < self.form.cleaned_data.get('normal_rating', 10):
            # green
            return '#90EE90'

        elif value < self.form.cleaned_data.get('bad_rating', 30):
            # yellow
            return '#FFFF00'

        # red
        return '#FF4500'
