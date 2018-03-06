# -*- coding: utf-8 -*-
from collections import OrderedDict, defaultdict
import datetime
import time

from django.utils.timezone import utc

from base.exceptions import ReportException
from base.utils import parse_float
from reports import forms
from reports.jinjaglobals import date
from reports.utils import parse_timedelta, parse_wialon_report_datetime, \
    get_wialon_report_template_id, cleanup_and_request_report, exec_report, \
    get_report_rows, local_to_utc_time, utc_to_local_time
from reports.views.base import BaseReportView, WIALON_NOT_LOGINED, WIALON_USER_NOT_FOUND, \
    REPORT_ROW_HEIGHT
from snippets.jinjaglobals import date as date_format, floatformat
from ura.models import Job
from users.models import User
from wialon.api import get_units
from wialon.exceptions import WialonException


class DischargeView(BaseReportView):
    """Перерасход топлива"""
    form_class = forms.FuelDischargeForm
    template_name = 'reports/discharge.html'
    report_name = 'Отчет по перерасходу топлива'
    can_download = True

    def __init__(self, *args, **kwargs):
        super(DischargeView, self).__init__(*args, **kwargs)
        self.user = None
        self.overspanding_total = .0
        self.discharge_total = .0
        self.overspanding_count = 0

    def get_default_form(self):
        data = self.request.POST if self.request.method == 'POST' else {
            'dt_from': datetime.datetime.now().replace(hour=0, minute=0, second=0, tzinfo=utc),
            'dt_to': datetime.datetime.now().replace(hour=23, minute=59, second=59, tzinfo=utc),
            'overspanding_percentage': 5
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
            'driver_name': '',
            'kmu': .0,
            'discharge': {
                'place': '',
                'dt': '',
                'volume': .0
            },
            'consumption': {
                'standard_mileage': .0,
                'standard_worktime': .0,
                'standard_extra_device': .0,
                'fact_dut': .0
            },
            'overspanding': .0,
            'moto_hours': .0,
            'move_hours': .0,
            'details': []
        }

    def get_context_data(self, **kwargs):
        kwargs = super(DischargeView, self).get_context_data(**kwargs)
        form = kwargs['form']
        report_data = None

        if self.request.POST:
            report_data = OrderedDict()

            if form.is_valid():
                sess_id = self.request.session.get('sid')
                if not sess_id:
                    raise ReportException(WIALON_NOT_LOGINED)

                self.user = User.objects.filter(is_active=True)\
                    .filter(wialon_username=self.request.session.get('user')).first()

                if not self.user:
                    raise ReportException(WIALON_USER_NOT_FOUND)

                normal_ratio = 1 + (form.cleaned_data['overspanding_percentage'] / 100)

                try:
                    units_list = get_units(sess_id=sess_id, extra_fields=True)
                except WialonException as e:
                    raise ReportException(str(e))

                units_dict = OrderedDict((u['id'], u) for u in units_list)
                print('Всего ТС: %s' % len(units_dict))

                dt_from_utc = local_to_utc_time(form.cleaned_data['dt_from'], self.user.wialon_tz)
                dt_to_utc = local_to_utc_time(
                    form.cleaned_data['dt_to'].replace(second=59), self.user.wialon_tz
                )

                ura_user = self.user.ura_user if self.user.ura_user_id else self.user
                jobs = Job.objects.filter(
                    user=ura_user, date_begin__lt=dt_to_utc, date_end__gt=dt_from_utc
                ).order_by('date_begin', 'date_end')

                jobs_cache = defaultdict(list)
                for job in jobs:
                    try:
                        jobs_cache[int(job.unit_id)].append(job)
                    except ValueError:
                        pass

                template_id = get_wialon_report_template_id('discharge_individual', self.user)
                device_fields = defaultdict(lambda: {'extras': .0, 'idle': .0})

                i = 0
                for unit_id, unit in units_dict.items():
                    i += 1
                    unit_name = unit['name']
                    print('%s) %s' % (i, unit_name))

                    # норматив потребления доп.оборудования, л / час
                    extras_values = [
                        x['v'] for x in unit.get('fields', []) if x.get('n') == 'механизм'
                    ]
                    # норматив потребления на холостом ходу, л / час
                    idle_values = [
                        x['v'] for x in unit.get('fields', []) if x.get('n') == 'хх'
                    ]

                    if extras_values:
                        try:
                            device_fields[unit_name]['extras'] = float(extras_values[0])
                        except ValueError:
                            pass

                    if idle_values:
                        try:
                            device_fields[unit_name]['idle'] = float(idle_values[0])
                        except ValueError:
                            pass

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

                    cleanup_and_request_report(self.user, template_id, sess_id=sess_id)

                    r = exec_report(
                        self.user, template_id,
                        dt_from, dt_to,
                        sess_id=sess_id, object_id=unit_id
                    )

                    wialon_report_rows = {}
                    for table_index, table_info in enumerate(r['reportResult']['tables']):
                        rows = get_report_rows(
                            self.user,
                            table_index,
                            table_info['rows'],
                            level=2 if table_info['name'] == 'unit_thefts' else 1,
                            sess_id=sess_id
                        )

                        wialon_report_rows[table_info['name']] = [row['c'] for row in rows]
                        print(table_info['name'])

                    for period in report_row['periods']:
                        for row in wialon_report_rows.get('unit_digital_sensors', []):
                            row_dt_from, row_dt_to = self.parse_wialon_report_datetime(row)
                            if row_dt_to is None:
                                row_dt_to = period['dt_to']

                            if period['dt_from'] < row_dt_from and period['dt_to'] > row_dt_to:
                                delta = min(row_dt_to, period['dt_to']) - \
                                        max(row_dt_from, period['dt_from'])
                                period['kmu'] += delta.total_seconds()

                        period['kmu'] /= 3600.0

                        for row in wialon_report_rows.get('unit_thefts', []):
                            dt = parse_wialon_report_datetime(
                                row[1]['t'] if isinstance(row[1], dict) else row[1]
                            )
                            utc_dt = local_to_utc_time(dt, self.user.wialon_tz)
                            if period['dt_from'] <= utc_dt <= period['dt_to']:

                                place = row[0]['t'] if isinstance(row[0], dict) else (row[0] or '')
                                if place and not period['discharge']['place']:
                                    period['discharge']['place'] = place

                                if not period['discharge']['dt']:
                                    period['discharge']['dt'] = dt

                                try:
                                    volume = float(row[2].split(' ')[0] if row[2] else .0)
                                except ValueError:
                                    volume = .0

                                period['discharge']['volume'] += volume
                                self.discharge_total += volume
                                self.overspanding_count += 1

                                period['details'].append({
                                    'place': place,
                                    'dt':  dt,
                                    'volume': volume
                                })

                        extras_value = device_fields.get(unit_name, {}).get('extras', .0)
                        idle_value = device_fields.get(unit_name, {}).get('idle', .0)

                        for row in wialon_report_rows.get('unit_engine_hours', []):
                            row_dt_from, row_dt_to = self.parse_wialon_report_datetime(row)
                            if row_dt_to is None:
                                row_dt_to = period['dt_to']

                            if period['dt_from'] < row_dt_from and period['dt_to'] > row_dt_to:
                                delta = (
                                    min(row_dt_to, period['dt_to']) -
                                    max(row_dt_from, period['dt_from'])
                                ).total_seconds()

                                if not delta:
                                    print('empty motohours period')
                                    continue

                                total_delta = (row_dt_to - row_dt_from).total_seconds()

                                period['moto_hours'] += delta / 3600.0
                                # доля моточасов в периоде и общих моточасов в строке
                                # данный множитель учтем в расчетах потребления
                                moto_ratio = 1
                                if total_delta > 0:
                                    moto_ratio = delta / total_delta

                                try:
                                    period['consumption']['fact_dut'] += (
                                        float(parse_float(row[3])) if row[3] else .0
                                    ) * moto_ratio

                                except ValueError:
                                    pass

                                try:
                                    period['consumption']['standard_mileage'] += (
                                        float(parse_float(row[4])) if row[4] else .0
                                    ) * moto_ratio

                                except ValueError:
                                    pass

                                period['move_hours'] += parse_timedelta(row[5]).total_seconds() \
                                    * moto_ratio / 3600.0

                        if idle_value:
                            period['consumption']['standard_worktime'] = max(
                                period['moto_hours'] - period['move_hours']
                                - period['kmu'], .0
                            ) * idle_value

                        if extras_value:
                            period['consumption']['standard_extra_device'] = \
                                period['kmu'] * extras_value

                        total_standards = period['consumption']['standard_extra_device'] \
                            + period['consumption']['standard_worktime'] \
                            + period['consumption']['standard_mileage']

                        if total_standards:
                            ratio = period['consumption']['fact_dut'] / total_standards
                            if ratio >= normal_ratio:
                                overspanding = period['consumption']['fact_dut'] \
                                   - total_standards

                                period['overspanding'] = overspanding
                                self.overspanding_total += overspanding

                        period['dt_from'] = utc_to_local_time(
                            period['dt_from'], self.user.wialon_tz
                        )
                        period['dt_to'] = utc_to_local_time(period['dt_to'], self.user.wialon_tz)

                if report_data:
                    for k, v in report_data.items():
                        v['periods'] = [
                            p for p in v['periods']
                            if p['discharge']['volume'] > .0 or p['overspanding'] > 0
                        ]

                    report_data = OrderedDict(
                        (k, v) for k, v in report_data.items() if v['periods']
                    )

        kwargs.update(
            discharge_total=self.discharge_total,
            enumerate=enumerate,
            overspanding_count=self.overspanding_count,
            overspanding_total=self.overspanding_total,
            report_data=report_data,
            today=datetime.date.today()
        )

        return kwargs

    def parse_wialon_report_datetime(self, row):
        row_dt_from = local_to_utc_time(
            parse_wialon_report_datetime(
                row[0]['t'] if isinstance(row[0], dict) else row[0]
            ), self.user.wialon_tz
        )
        row_dt_to = local_to_utc_time(
            parse_wialon_report_datetime(
                row[1]['t'] if isinstance(row[1], dict) else row[1]
            ), self.user.wialon_tz
        )

        return row_dt_from, row_dt_to

    def write_xls_data(self, worksheet, context):
        worksheet = super(DischargeView, self).write_xls_data(worksheet, context)
        worksheet.set_portrait(False)

        worksheet.col(0).width = 5000
        worksheet.col(1).width = 8000
        worksheet.col(2).width = 5000
        worksheet.col(3).width = 6000
        worksheet.col(4).width = 9000
        worksheet.col(5).width = 2200
        worksheet.col(6).width = 3000
        worksheet.col(7).width = 4000
        worksheet.col(8).width = 4000
        worksheet.col(9).width = 2700
        worksheet.col(10).width = 3200

        # header
        worksheet.write_merge(
            1, 1, 0, 10, 'За период: %s - %s' % (
                date_format(context['cleaned_data']['dt_from'], 'd.m.Y H:i'),
                date_format(context['cleaned_data']['dt_to'], 'd.m.Y H:i')
            )
        )
        worksheet.write_merge(
            2, 2, 0, 10, 'Итого перерасход, л: %s' % floatformat(
                context.get('overspanding_total', 0) or 0, -2
            ),
            style=self.styles['left_center_style']
        )
        worksheet.write_merge(
            3, 3, 0, 10, 'Итого слив, л: %s' % floatformat(
                context.get('discharge_total', 0) or 0, -2
            ),
            style=self.styles['left_center_style']
        )
        worksheet.write_merge(
            4, 4, 0, 10, 'Зафиксировано случаев слива: %s' % context.get('overspanding_count', 0),
            style=self.styles['left_center_style']
        )
        worksheet.write_merge(
            5, 5, 0, 10, 'Список случаев перерасхода топлива на дату:',
            style=self.styles['right_center_style']
        )

        # head
        worksheet.write_merge(6, 7, 0, 0, ' Время', style=self.styles['border_center_style'])
        worksheet.write_merge(
            6, 7, 1, 1, ' Гос№ ТС', style=self.styles['border_center_style']
        )
        worksheet.write_merge(
            6, 7, 2, 2, ' Плановый график\nработы водителя\n(время с - время по)',
            style=self.styles['border_center_style']
        )
        worksheet.write_merge(
            6, 7, 3, 3, ' ФИО водителя', style=self.styles['border_center_style']
        )
        worksheet.write_merge(
            6, 6, 4, 5, ' Событие слив', style=self.styles['border_center_style']
        )
        worksheet.write(
            7, 4, ' Место/\nгеозона', style=self.styles['border_center_style']
        )
        worksheet.write(
            7, 5, ' Объем', style=self.styles['border_center_style']
        )
        worksheet.write_merge(
            6, 6, 6, 9, ' Израсходовано топлива за запрашиваемый период, л',
            style=self.styles['border_center_style']
        )
        worksheet.write(
            7, 6, ' По норме\nот пробега**',
            style=self.styles['border_center_style']
        )
        worksheet.write(
            7, 7, ' По норме\nот времени\nработы на ХХ***',
            style=self.styles['border_center_style']
        )
        worksheet.write(
            7, 8, ' По норме\nот работы доп.\nоборудования****',
            style=self.styles['border_center_style']
        )
        worksheet.write(
            7, 9, ' По факту\nс ДУТ',
            style=self.styles['border_center_style']
        )
        worksheet.write_merge(
            6, 7, 10, 10, ' *Перерасход,\nл', style=self.styles['border_center_style']
        )

        for i in range(11):
            worksheet.write(8, i, str(i + 1), style=self.styles['border_center_style'])

        for i in range(1, 9):
            worksheet.row(i).height = REPORT_ROW_HEIGHT
            worksheet.row(i).level = 1
        worksheet.row(7).height = 800

        # body
        i = 8
        for row in context['report_data'].values():
            for period in row['periods']:
                i += 1
                worksheet.row(i).level = 1
                # worksheet.row(i).collapse = 2

                worksheet.write(i, 0, '%s - %s' % (
                    date(period['dt_from'], 'Y-m-d H:i:s'),
                    date(period['dt_to'], 'Y-m-d H:i:s')
                ), style=self.styles['border_left_style'])

                worksheet.write(i, 1, row['unit_name'], style=self.styles['border_left_style'])

                job_period = ''
                if period.get('job'):
                    job_period = '%s - %s' % (
                        date(period['dt_from'], 'Y-m-d H:i:s'),
                        date(period['dt_to'], 'Y-m-d H:i:s')
                    )
                worksheet.write(i, 2, job_period, style=self.styles['border_left_style'])

                worksheet.write(
                    i, 3, period['job'].driver_fio if period.get('job') else '',
                    style=self.styles['border_left_style']
                )
                worksheet.write(
                    i, 4, period['discharge']['place'],
                    style=self.styles['border_left_style']
                )
                worksheet.write(
                    i, 5, floatformat(period['discharge']['volume'], 2) or '',
                    style=self.styles['border_right_style']
                )
                worksheet.write(
                    i, 6, floatformat(period['consumption']['standard_mileage'], 2) or '',
                    style=self.styles['border_right_style']
                )
                worksheet.write(
                    i, 7, floatformat(period['consumption']['standard_worktime'], 2) or '',
                    style=self.styles['border_right_style']
                )
                worksheet.write(
                    i, 8, floatformat(period['consumption']['standard_extra_device'], 2) or '',
                    style=self.styles['border_right_style']
                )
                worksheet.write(
                    i, 9, floatformat(period['consumption']['fact_dut'], 2) or '',
                    style=self.styles['border_right_style']
                )
                worksheet.write(
                    i, 10, floatformat(period['overspanding'], 2) or '',
                    style=self.styles['border_right_style']
                )
                worksheet.row(i).height = 520

                for detail in period['details']:
                    i += 1
                    worksheet.row(i).level = 2
                    # worksheet.row(i).collapse = 2

                    worksheet.write(
                        i, 0, date(detail['dt'], 'Y-m-d H:i:s') or '',
                        style=self.styles['border_left_style']
                    )

                    worksheet.write(i, 1, row['unit_name'], style=self.styles['border_left_style'])

                    job_period = ''
                    if period.get('job'):
                        job_period = '%s - %s' % (
                            date(period['dt_from'], 'Y-m-d H:i:s'),
                            date(period['dt_to'], 'Y-m-d H:i:s')
                        )
                    worksheet.write(i, 2, job_period, style=self.styles['border_left_style'])

                    worksheet.write(
                        i, 3, period['job'].driver_fio if period.get('job') else '',
                        style=self.styles['border_left_style']
                    )
                    worksheet.write(
                        i, 4, detail['place'] or '',
                        style=self.styles['border_left_style']
                    )
                    worksheet.write(
                        i, 5, floatformat(detail['volume'], 2) or '',
                        style=self.styles['border_right_style']
                    )
                    worksheet.write(i, 6, '', style=self.styles['border_right_style'])
                    worksheet.write(i, 7, '', style=self.styles['border_right_style'])
                    worksheet.write(i, 8, '', style=self.styles['border_right_style'])
                    worksheet.write(i, 9, '', style=self.styles['border_right_style'])
                    worksheet.write(i, 10, '', style=self.styles['border_right_style'])
                    worksheet.row(i).height = 520

        return worksheet
