# -*- coding: utf-8 -*-
from collections import OrderedDict
import datetime

from base.exceptions import ReportException
from reports import forms
from reports.utils import parse_timedelta, get_drivers_fio, parse_wialon_report_datetime, \
    get_wialon_discharge_report_template_id, get_period, cleanup_and_request_report, exec_report, \
    get_report_rows
from reports.views.base import BaseReportView, WIALON_NOT_LOGINED, WIALON_USER_NOT_FOUND
from ura.wialon.api import get_units_list
from ura.wialon.exceptions import WialonException


class DischargeView(BaseReportView):
    """Перерасход топлива"""
    form = forms.FuelDischargeForm
    template_name = 'reports/discharge.html'
    report_name = 'Отчет по перерасходу топлива'
    OVERSPANDING_COEFF = 0.05

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
                'standard_mileage': '',
                'standard_worktime': '',
                'standard_extra_device': '',
                'fact': ''
            },
            'overspanding': '',
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
                sess_id = form.cleaned_data.get('sid')
                if not sess_id:
                    raise ReportException(WIALON_NOT_LOGINED)

                user = form.cleaned_data.get('user')
                if not user:
                    raise ReportException(WIALON_USER_NOT_FOUND)

                try:
                    units_list = get_units_list(sess_id=sess_id, extra_fields=True)
                except WialonException as e:
                    raise ReportException(str(e))

                dt_from, dt_to = get_period(
                    form.cleaned_data['dt_from'],
                    form.cleaned_data['dt_to'],
                    user.wialon_tz
                )

                extra_device_standards = {}
                for unit in units_list:
                    extra_standard = [
                        x['v'] for x in unit.get('fields', []) if x.get('n') == 'механизм'
                    ]

                    if extra_standard:
                        try:
                            extra_device_standards[unit['name']] = float(extra_standard[0])
                        except ValueError:
                            pass

                cleanup_and_request_report(
                    user, get_wialon_discharge_report_template_id(user), sess_id=sess_id
                )

                r = exec_report(
                    user,
                    get_wialon_discharge_report_template_id(user),
                    dt_from,
                    dt_to,
                    sess_id=sess_id
                )

                for table_index, table_info in enumerate(r['reportResult']['tables']):

                    rows = get_report_rows(
                        user,
                        table_index,
                        table_info,
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

                            report_data[key]['driver_name'] = get_drivers_fio(
                                units_list,
                                key,
                                report_data[key]['plan_worktime'][0],
                                report_data[key]['plan_worktime'][1],
                                user.ura_tz
                            ) or ''

                        report_row = report_data[key]

                        if table_info['name'] == 'unit_group_trips' and data[4]:
                            report_row['driver_name'] = data[4]

                        elif table_info['name'] == 'unit_group_thefts':
                            report_row['discharge']['place'] = data[1]['t'] \
                                if data[1] and isinstance(data[1], dict) else ''

                            report_row['discharge']['dt'] = parse_wialon_report_datetime(
                                data[2]['t']
                            ) if data[2] and isinstance(data[2], dict) else ''

                            try:
                                report_row['discharge']['volume'] = float(data[3].split(' ')[0]) \
                                    if data[3] else ''
                            except ValueError:
                                report_row['discharge']['volume'] = 0.0

                            if len(data[3].replace('-', '')) > 0:
                                discharge_total += float(data[3].split(' ')[0])

                            if data[4]:
                                overspanding_count += int(data[4])

                            details = row['r']
                            if len(details) > 1:
                                for detail in details:
                                    detail_data = detail['c']
                                    try:
                                        detail_volume = float(detail_data[3].split(' ')[0])\
                                            if detail_data[3] else ''
                                    except ValueError:
                                        detail_volume = 0.0

                                    report_row['details'].append({
                                        'place': detail_data[1]['t']
                                        if detail_data[1] and isinstance(detail_data[1], dict)
                                        else '',
                                        'dt': parse_wialon_report_datetime(
                                            detail_data[2]['t']
                                        ) if detail_data[2] and isinstance(detail_data[2], dict)
                                        else '',
                                        'volume': detail_volume
                                    })

                        elif table_info['name'] == 'unit_group_generic':
                            try:
                                standard = report_row['consumption']['standard_mileage'] = \
                                    report_row['consumption']['standard_worktime'] = \
                                    float(data[4].split(' ')[0]) if data[4] else 0.0
                            except ValueError:
                                standard = report_row['consumption']['standard_mileage'] = \
                                    report_row['consumption']['standard_worktime'] = 0

                            fact = report_row['consumption']['fact'] = \
                                (float(data[3].split(' ')[0]) if data[3] else 0.0)

                            extra_standard = extra_device_standards.get(key, 0.0)
                            if extra_standard:
                                motohours = parse_timedelta(data[2]).seconds / (60.0 * 60.0)
                                extra_standard *= motohours

                                report_row['consumption']['standard_extra_device'] = extra_standard
                                standard += extra_standard

                            if standard and fact / standard > (1.0 + self.OVERSPANDING_COEFF):
                                report_row['overspanding'] = (fact / standard) * 100.0
                                overspanding_total += fact - standard

        kwargs.update(
            report_data=report_data,
            today=datetime.date.today(),
            discharge_total=discharge_total,
            overspanding_count=overspanding_count,
            overspanding_total=overspanding_total
        )

        return kwargs
