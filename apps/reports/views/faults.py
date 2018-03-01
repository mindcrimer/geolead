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
    can_download = True

    def __init__(self, *args, **kwargs):
        super(FaultsView, self).__init__(*args, **kwargs)
        self.report_data = None
        self.sensors_report_data = {}
        self.last_data = {}
        self.stats = {
            'total': set(),
            'broken': set()
        }
        self.mapping = {
            'ВСЕ': {},
            'Геолокация': {},
            'Свет фар': {},
            'Ремень': {},
            'Зажигание': {},
            'ДУТ': {},
            'Напряжение АКБ': {}
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

                sensors_template_id = get_wialon_report_template_id('sensors', self.user)
                last_data_template_id = get_wialon_report_template_id('last_data', self.user)

                dt_from, dt_to = get_period(
                    dt_from_local, dt_to_local, self.user.wialon_tz
                )
                cleanup_and_request_report(self.user, last_data_template_id, sess_id=sess_id)
                r = exec_report(self.user, last_data_template_id, dt_from, dt_to, sess_id=sess_id)

                for table_index, table_info in enumerate(r['reportResult']['tables']):
                    rows = get_report_rows(
                        self.user,
                        table_index,
                        table_info['rows'],
                        level=1,
                        sess_id=sess_id
                    )

                    if table_info['name'] == 'unit_group_location':
                        self.last_data = {r['c'][0]: r['c'][1:] for r in rows}
                        break

                jobs = Job.objects.filter(
                    user=self.user, date_begin__lt=dt_to_utc, date_end__gte=dt_from_utc
                )

                for i, job in enumerate(jobs):
                    try:
                        unit_name = units_cache.get(int(job.unit_id))
                    except (ValueError, AttributeError, TypeError):
                        unit_name = ''

                    if not unit_name:
                        print('ТС не найден! %s' % job.unit_id)
                        continue

                    if unit_name != 'FUCHS MHL 350 66СК9907':
                        continue

                    print('%s) %s' % (i, unit_name))
                    self.stats['total'].add(unit_name)

                    job_local_date_begin = utc_to_local_time(
                        job.date_begin - job_extra_offset, self.user.wialon_tz
                    )
                    job_local_date_to = utc_to_local_time(
                        job.date_end + job_extra_offset, self.user.wialon_tz
                    )
                    dt_from, dt_to = get_period(
                        job_local_date_begin, job_local_date_to, self.user.wialon_tz
                    )
                    self.sensors_report_data = {}
                    cleanup_and_request_report(self.user, sensors_template_id, sess_id=sess_id)
                    r = exec_report(
                        self.user, sensors_template_id, dt_from, dt_to,
                        sess_id=sess_id, object_id=int(job.unit_id)
                    )

                    report_tables = {}
                    for table_index, table_info in enumerate(r['reportResult']['tables']):
                        label = table_info['label'].split('(')[0].strip()

                        if table_info['name'] != 'unit_sensors_tracing':
                            continue

                        report_tables[label] = {
                            'index': table_index,
                            'rows': table_info['rows']
                        }

                    if 'ВСЕ' not in report_tables:
                        self.add_report_row(
                            job, unit_name, 'Нет данных от блока мониторинга'
                        )
                        continue

                    for field in self.mapping.keys():
                        if field == 'ВСЕ':
                            continue

                        if field not in report_tables:
                            self.add_report_row(
                                job, unit_name, 'Нет данных по датчику "%s"' % field
                            )
                            continue

                        attempts = (10, 100, max(report_tables[field]['rows'], 10000))
                        for attempt, rows_limit in enumerate(attempts):
                            rows = get_report_rows(
                                self.user,
                                report_tables[field]['index'],
                                # для всех датчиков достаточно и 10 записей
                                rows_limit,
                                level=1,
                                sess_id=sess_id
                            )

                            data = [r['c'] for r in rows]

                            if self.analyze_sensor_data(field, data):
                                break
                            # если в последней попытке тоже не нашел
                            elif attempt == len(attempts) - 1:
                                self.add_report_row(
                                    job, unit_name,
                                    'Датчик "%s" отправляет одни и те же '
                                    'данные в течение смены' % field
                                )

        self.stats['total'] = len(self.stats['total'])
        self.stats['broken'] = len(self.stats['broken'])

        kwargs.update(
            stats=self.stats,
            report_data=self.report_data,
            render_background=render_background
        )

        return kwargs

    @staticmethod
    def analyze_sensor_data(label, data):
        """Ищем корректность датчика"""
        print(label)
        if label == 'Геолокация':
            values = set(
                map(
                    lambda x: x[4]['t'] if (
                        x[4] and isinstance(x[4], dict) and 't' in x[4]
                    ) else '',
                    data)
            )
        else:
            values = set(map(lambda x: x[3], data))

        if len(values) > 1:
            return True

    def add_report_row(self, job, unit_name, fault, place=None, dt=None,
                       sum_broken_work_time=None):
        report_row = self.get_new_grouping()
        self.stats['broken'].add(unit_name)

        if place is None and dt is None:
            dt, place = self.get_last_data(unit_name)

        report_row.update(
            unit=unit_name,
            fault=fault,
            place=place,
            dt=dt,
            driver_name=job.driver_fio
        )

        if sum_broken_work_time is None:
            report_row['sum_broken_work_time'] = self.get_sum_broken_work_time(
                job.unit_id,
                local_to_utc_time(dt, self.user.wialon_tz), job.date_end
            )

        self.report_data.append(report_row)

    def get_last_data(self, unit_name):
        data = self.last_data.get(unit_name)
        if data and len(data) > 1:
            dt, place = data[0], data[2]

            if isinstance(dt, dict):
                dt = datetime.datetime.utcfromtimestamp(dt['v'])
                dt = utc_to_local_time(dt, self.user.wialon_tz)
            else:
                dt = parse_wialon_report_datetime(dt)

            if isinstance(place, dict) and 't' in place:
                place = place['t']

            return dt, place

        return '', ''

    def get_sum_broken_work_time(self, unit_id, dt_from, dt_to):
        if not dt_from or not dt_to:
            return None

        sum_broken_work_time = 0
        jobs = Job.objects.filter(
            user=self.user, unit_id=unit_id, date_begin__lt=dt_to, date_end__gte=dt_from
        )

        for job in jobs:
            intersects_period = max(dt_from, job.date_begin), min(dt_to, job.date_end)
            sum_broken_work_time += (intersects_period[1] - intersects_period[0]).seconds

        if sum_broken_work_time:
            return round(sum_broken_work_time / 3600.0, 2)
