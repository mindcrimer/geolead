# -*- coding: utf-8 -*-
from collections import OrderedDict, defaultdict
import datetime

from django.utils.timezone import utc

from base.exceptions import ReportException
from base.utils import parse_float
from reports import forms
from reports.utils import parse_timedelta, get_drivers_fio, parse_wialon_report_datetime, \
    get_wialon_report_template_id, get_period, cleanup_and_request_report, exec_report, \
    get_report_rows
from reports.views.base import BaseReportView, WIALON_NOT_LOGINED, WIALON_USER_NOT_FOUND
from users.models import User
from wialon.api import get_units
from wialon.exceptions import WialonException


class DischargeView(BaseReportView):
    """Перерасход топлива"""
    form_class = forms.FuelDischargeForm
    template_name = 'reports/discharge.html'
    report_name = 'Отчет по перерасходу топлива'

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
            'plan_worktime': ('', ''),
            'driver_name': '',
            'discharge': {
                'place': '',
                'dt': '',
                'volume': ''
            },
            'consumption': {
                'standard_mileage': .0,
                'standard_worktime': .0,
                'standard_extra_device': .0,
                'fact_dut': .0
            },
            'overspanding': .0,
            'moto_hours': 0,
            'move_hours': 0,
            'details': []
        }

    def get_context_data(self, **kwargs):
        kwargs = super(DischargeView, self).get_context_data(**kwargs)
        form = kwargs['form']
        report_data = None
        overspanding_total = .0
        discharge_total = .0
        overspanding_count = 0

        if self.request.POST:
            report_data = OrderedDict()

            if form.is_valid():
                sess_id = self.request.session.get('sid')
                if not sess_id:
                    raise ReportException(WIALON_NOT_LOGINED)

                user = User.objects.filter(is_active=True)\
                    .filter(wialon_username=self.request.session.get('user')).first()

                if not user:
                    raise ReportException(WIALON_USER_NOT_FOUND)

                try:
                    units_list = get_units(sess_id=sess_id, extra_fields=True)
                except WialonException as e:
                    raise ReportException(str(e))

                dt_from, dt_to = get_period(
                    form.cleaned_data['dt_from'],
                    form.cleaned_data['dt_to'].replace(second=59),
                    user.wialon_tz
                )

                device_fields = defaultdict(lambda: {'extras': .0, 'idle': .0, 'kmu': 0})
                template_id = get_wialon_report_template_id('kmu', user)
                for unit in units_list:
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
                            device_fields[unit['name']]['extras'] = float(extras_values[0])
                        except ValueError:
                            pass

                    if idle_values:
                        try:
                            device_fields[unit['name']]['idle'] = float(idle_values[0])
                        except ValueError:
                            pass

                    # если есть нормативы холостого хожда и КМУ, узнаем время работы КМУ
                    if device_fields[unit['name']]['idle'] \
                            and device_fields[unit['name']]['extras']:

                        cleanup_and_request_report(user, template_id, sess_id=sess_id)

                        r = exec_report(
                            user, template_id, dt_from, dt_to, object_id=unit['id'],
                            sess_id=sess_id
                        )

                        if r['reportResult']['tables']:
                            rows = get_report_rows(
                                user, table_index=0, rows=1, level=0, sess_id=sess_id
                            )
                            if rows and 'c' in rows[0] and len(rows[0]['c']) > 4:
                                device_fields[unit['name']]['kmu'] = parse_timedelta(
                                    rows[0]['c'][4]
                                ).seconds / 3600.0

                template_id = get_wialon_report_template_id('discharge', user)
                cleanup_and_request_report(user, template_id, sess_id=sess_id)

                r = exec_report(user, template_id, dt_from, dt_to, sess_id=sess_id)

                normal_ratio = 1 + (form.cleaned_data['overspanding_percentage'] / 100)

                for table_index, table_info in enumerate(r['reportResult']['tables']):
                    rows = get_report_rows(
                        user,
                        table_index,
                        table_info['rows'],
                        level=2 if table_info['name'] == 'unit_group_thefts' else 1,
                        sess_id=sess_id
                    )

                    for row in rows:
                        data = row['c']
                        key = data[0]

                        if key not in report_data:
                            report_data[key] = self.get_new_grouping()
                            report_data[key]['plan_worktime'] = (
                                r['reportResult']['stats'][0][1],
                                r['reportResult']['stats'][1][1]
                            )

                        report_row = report_data[key]

                        if table_info['name'] == 'unit_group_thefts':
                            report_row['discharge']['place'] = ''
                            if data[1]:
                                if isinstance(data[1], dict):
                                    report_row['discharge']['place'] = data[1]['t']
                                else:
                                    report_row['discharge']['place'] = data[1]

                            discharge_dt = ''
                            if data[2]:
                                if isinstance(data[2], dict):
                                    discharge_dt = parse_wialon_report_datetime(data[2]['t'])
                                else:
                                    discharge_dt = parse_wialon_report_datetime(data[2])

                            report_row['discharge']['dt'] = discharge_dt

                            try:
                                report_row['discharge']['volume'] = float(data[3].split(' ')[0]) \
                                    if data[3] else ''
                            except ValueError:
                                report_row['discharge']['volume'] = .0

                            if len(data[3].replace('-', '')) > 0:
                                discharge_total += float(data[3].split(' ')[0])

                            if data[4]:
                                overspanding_count += int(data[4])

                            details = row['r']
                            for detail in details:
                                detail_data = detail['c']
                                try:
                                    detail_volume = float(detail_data[3].split(' ')[0])\
                                        if detail_data[3] else ''
                                except ValueError:
                                    detail_volume = .0

                                detail_place = ''
                                if detail_data[1]:
                                    if isinstance(detail_data[1], dict):
                                        detail_place = detail_data[1]['t']
                                    else:
                                        detail_place = detail_data[1]

                                detail_dt = ''
                                if detail_data[2]:
                                    if isinstance(detail_data[2], dict):
                                        detail_dt = detail_data[2]['t']
                                    else:
                                        detail_dt = detail_data[2]

                                    detail_dt = parse_wialon_report_datetime(detail_dt)

                                report_row['details'].append({
                                    'place': detail_place,
                                    'dt':  detail_dt,
                                    'volume': detail_volume
                                })

                        elif table_info['name'] == 'unit_group_trips':
                            if len(data) > 4 and data[4]:
                                report_row['driver_name'] = data[4]
                            else:
                                report_row['driver_name'] = get_drivers_fio(
                                    units_list,
                                    key,
                                    report_data[key]['plan_worktime'][0],
                                    report_data[key]['plan_worktime'][1],
                                    user.ura_tz
                                ) or ''

                        elif table_info['name'] == 'unit_group_generic':
                            if len(data) > 2 and data[2]:
                                report_row['moto_hours'] = parse_timedelta(
                                    data[2]
                                ).seconds / 3600.0

                            if len(data) > 3 and data[3]:
                                try:
                                    report_row['consumption']['fact_dut'] = \
                                        float(parse_float(data[3])) if data[3] else .0

                                except ValueError:
                                    pass

                            if len(data) > 4 and data[4]:
                                try:
                                    report_row['consumption']['standard_mileage'] = \
                                        float(parse_float(data[4])) if data[4] else .0

                                except ValueError:
                                    pass

                            if len(data) > 5 and data[5]:
                                report_row['move_hours'] = parse_timedelta(
                                    data[5]
                                ).seconds / 3600.0

                            extras_value = device_fields.get(key, {}).get('extras', .0)
                            idle_value = device_fields.get(key, {}).get('idle', .0)
                            kmu_hours = device_fields.get(key, {}).get('kmu', .0)

                            if idle_value:
                                report_row['consumption']['standard_worktime'] = (
                                    report_row['moto_hours'] - report_row['move_hours'] - kmu_hours
                                ) * idle_value

                            if extras_value:
                                report_row['consumption']['standard_extra_device'] = \
                                    kmu_hours * extras_value

                            total_standards = report_row['consumption']['standard_extra_device'] \
                                + report_row['consumption']['standard_worktime'] \
                                + report_row['consumption']['standard_mileage']

                            if total_standards:
                                ratio = report_row['consumption']['fact_dut'] / total_standards
                                if ratio >= normal_ratio:
                                    overspanding = report_row['consumption']['fact_dut'] \
                                       - total_standards

                                    report_row['overspanding'] = overspanding
                                    overspanding_total += overspanding

                if report_data:
                    report_data = OrderedDict(
                        (k, v) for k, v in report_data.items()
                        if v['discharge']['volume'] > .0 or v['overspanding'] > 0
                    )

        kwargs.update(
            report_data=report_data,
            today=datetime.date.today(),
            discharge_total=discharge_total,
            overspanding_count=overspanding_count,
            overspanding_total=overspanding_total
        )

        return kwargs

    def write_xls_data(self, worksheet, context):
        worksheet = super(DischargeView, self).write_xls_data(worksheet, context)

        return worksheet
