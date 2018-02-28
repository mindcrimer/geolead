# -*- coding: utf-8 -*-
import datetime

from django.utils.timezone import utc

from base.exceptions import ReportException
from reports import forms
from reports.jinjaglobals import render_background
from reports.utils import get_period, local_to_utc_time, cleanup_and_request_report, \
    get_wialon_report_template_id, exec_report, get_report_rows, utc_to_local_time, \
    parse_wialon_report_datetime
from reports.views.base import BaseReportView, WIALON_NOT_LOGINED, WIALON_USER_NOT_FOUND
from ura.models import Job
from users.models import User
from wialon.api import get_units


class FaultsView(BaseReportView):
    """Отчет о состоянии оборудования ССМТ"""
    form = forms.FaultsForm
    template_name = 'reports/faults.html'
    report_name = 'Отчет о состоянии оборудования ССМТ'

    def __init__(self, *args, **kwargs):
        super(FaultsView, self).__init__(*args, **kwargs)
        self.report_data = None
        self.sensors_report_data = {}
        self.stats = {
            'total': set(),
            'broken': set()
        }
        self.user = None

    def get_default_form(self):
        data = self.request.POST if self.request.method == 'POST' else {
            'dt': datetime.datetime.now().replace(hour=0, minute=0, second=0, tzinfo=utc),
            'job_extra_offset': 2
        }
        return self.form(data)

    @staticmethod
    def get_new_grouping():
        return {
            'unit': '',
            'place': '',
            'dt': '',
            'driver_name': '',
            'sum_broken_work_time': '',
            'fault': ''
        }

    def add_report_row(self, unit_name, fault, place='', dt='', driver_name='',
                       sum_broken_work_time=''):
        report_row = self.get_new_grouping()
        self.stats['broken'].add(unit_name)
        report_row.update(
            unit=unit_name,
            fault=fault,
            place=place,
            dt=dt,
            driver_name=driver_name,
            sum_broken_work_time=sum_broken_work_time
        )

    def get_last_data(self, unit):
        data = self.sensors_report_data['unit_group_location'].get(unit)
        if data and len(data) > 1:
            dt, place = data[0], data[1]

            if isinstance(dt, dict):
                dt = datetime.datetime.utcfromtimestamp(dt['v'])
                dt = utc_to_local_time(dt, self.user.wialon_tz)
            else:
                dt = parse_wialon_report_datetime(dt)

            if isinstance(place, dict) and 't' in place:
                place = place['t']

            return dt, place

        return '', ''

    def get_context_data(self, **kwargs):
        kwargs = super(FaultsView, self).get_context_data(**kwargs)
        form = kwargs['form']
        kwargs['today'] = datetime.date.today()

        if self.request.POST:
            self.report_data = []

            if form.is_valid():
                sess_id = self.request.session.get('sid')
                if not sess_id:
                    raise ReportException(WIALON_NOT_LOGINED)

                self.user = User.objects.filter(is_active=True) \
                    .filter(wialon_username=self.request.session.get('user')).first()

                if not self.user:
                    raise ReportException(WIALON_USER_NOT_FOUND)

                report_date = form.cleaned_data['dt']
                job_extra_offset = datetime.timedelta(
                    seconds=form.cleaned_data['job_extra_offset'] * 60 * 60
                )

                units_list = get_units(sess_id=sess_id)
                units_cache = {u['id']: u['name'] for u in units_list}

                dt_from_local = datetime.datetime.combine(report_date, datetime.time(0, 0, 0))
                dt_to_local = datetime.datetime.combine(report_date, datetime.time(23, 59, 59))

                dt_from_utc = local_to_utc_time(dt_from_local, self.user.wialon_tz)
                dt_to_utc = local_to_utc_time(dt_to_local, self.user.wialon_tz)

                dt_from_offset = dt_from_local - job_extra_offset
                dt_to_offset = dt_to_local + job_extra_offset

                dt_from, dt_to = get_period(dt_from_offset, dt_to_offset, self.user.wialon_tz)

                template_id = get_wialon_report_template_id('sensors', self.user)

                cleanup_and_request_report(self.user, template_id, sess_id=sess_id)
                r = exec_report(self.user, template_id, dt_from, dt_to, sess_id=sess_id)

                jobs = Job.objects.filter(
                    user=self.user, date_begin__lt=dt_to_utc, date_end__gte=dt_from_utc
                )

                for table_index, table_info in enumerate(r['reportResult']['tables']):
                    rows = get_report_rows(
                        self.user,
                        table_index,
                        table_info['rows'],
                        level=2 if table_info['name'] == 'unit_group_sensors_tracing' else 1,
                        sess_id=sess_id
                    )

                    if table_info['name'] == 'unit_group_sensors_tracing':
                        self.sensors_report_data[table_info['name']] = {
                            r['c'][0]: [x['c'] for x in r['r']] for r in rows
                        }
                    else:
                        self.sensors_report_data[table_info['name']] = {
                            r['c'][0]: r['c'][1:] for r in rows
                        }

                    del rows

                for job in jobs:
                    try:
                        unit_name = units_cache.get(int(job.unit_id))
                    except (ValueError, AttributeError, TypeError):
                        unit_name = ''

                    if not unit_name:
                        print('ТС не найден! %s' % job.unit_id)
                        continue

                    self.stats['total'].add(unit_name)

                    messages = self.sensors_report_data['unit_group_sensors_tracing'].get(
                        unit_name
                    )

                    # когда вообще нет сообщений
                    if not messages:
                        dt, place = self.get_last_data(unit_name)
                        self.add_report_row(
                            unit_name, 'Нет данных от блока мониторинга',
                            place=place,
                            dt=dt
                        )
                        continue

        self.stats['total'] = len(self.stats['total'])
        self.stats['broken'] = len(self.stats['broken'])

        kwargs.update(
            stats=self.stats,
            report_data=self.report_data,
            render_background=render_background
        )

        return kwargs
