# -*- coding: utf-8 -*-
from collections import OrderedDict
from datetime import date
import json
import time

from django.conf import settings
from django.utils.timezone import utc

import requests

from reports import forms
from reports.utils import parse_timedelta, get_drivers_fio
from reports.views.base import BaseReportView, ReportException, WIALON_INTERNAL_EXCEPTION
from ura.wialon.api import get_units_list
from ura.wialon.auth import authenticate_at_wialon


class OverSpandingView(BaseReportView):
    """Перерасход топлива"""
    form = forms.FuelDischargeForm
    template_name = 'reports/over_spanding.html'
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
        kwargs = super(OverSpandingView, self).get_context_data(**kwargs)
        form = kwargs['form']
        report_data = None
        overspanding_total = .0
        discharge_total = .0
        overspanding_count = 0

        if kwargs['view'].request.POST:
            report_data = OrderedDict()

            if form.is_valid():
                sess_id = authenticate_at_wialon(settings.WIALON_TOKEN)
                units_list = get_units_list(
                    kwargs['view'].request.user, sess_id=sess_id, extra_fields=True
                )

                dt_from = form.cleaned_data['dt_from'].replace(tzinfo=utc)
                dt_to = form.cleaned_data['dt_to'].replace(tzinfo=utc)

                dt_from = int(time.mktime(dt_from.timetuple()))
                dt_to = int(time.mktime(dt_to.timetuple()))

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

                requests.post(
                    settings.WIALON_BASE_URL + '?svc=core/batch&sid=' + sess_id, {
                        'params': json.dumps({
                            'params': [
                                {
                                    'svc': 'report/cleanup_result',
                                    'params': {}
                                },
                                {
                                    'svc': 'report/get_report_data',
                                    'params': {
                                        'itemId': 15828651,  # 14175015,
                                        'col': ['8'],  # ['3'],
                                        'flags': 0
                                    }
                                }
                            ],
                            'flags': 0
                        }),
                        'sid': sess_id
                    }
                )

                res = requests.post(
                    settings.WIALON_BASE_URL + '?svc=report/exec_report&sid=' + sess_id, {
                        'params': json.dumps({
                            'reportResourceId': 15828651,  # 14175015,
                            'reportTemplateId': 8,  # 3,
                            'reportTemplate': None,
                            'reportObjectId': 15932813,  # 15826705,
                            'reportObjectSecId': 0,
                            'interval': {
                                'flags': 0,
                                'from': dt_from,
                                'to': dt_to
                            }
                        }),
                        'sid': sess_id
                    }
                )

                r = res.json()

                if 'error' in r:
                    raise ReportException(WIALON_INTERNAL_EXCEPTION)

                for index, table in enumerate(r['reportResult']['tables']):

                    rows = requests.post(
                        settings.WIALON_BASE_URL + '?svc=report/select_result_rows&sid=' +
                        sess_id, {
                            'params': json.dumps({
                                'tableIndex': index,
                                'config': {
                                    'type': 'range',
                                    'data': {
                                        'from': 0,
                                        'to': table['rows'] - 1,
                                        'level': 2 if table['name'] == 'unit_group_thefts' else 1
                                    }
                                }
                            }),
                            'sid': sess_id
                        }
                    ).json()

                    if 'error' in rows:
                        raise ReportException(WIALON_INTERNAL_EXCEPTION)

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
                                report_data[key]['plan_worktime'][1]
                            ) or ''

                        report_row = report_data[key]

                        if table['name'] == 'unit_group_trips' and data[4]:
                            report_row['driver_name'] = data[4]

                        elif table['name'] == 'unit_group_thefts':
                            report_row['discharge']['place'] = data[1]['t'] \
                                if data[1] and isinstance(data[1], dict) else ''

                            report_row['discharge']['dt'] = data[2]['t'] \
                                if data[2] and isinstance(data[2], dict) else ''

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
                                        'dt': detail_data[2]['t']
                                        if detail_data[2] and isinstance(detail_data[2], dict)
                                        else '',
                                        'volume': detail_volume
                                    })

                        elif table['name'] == 'unit_group_generic':
                            try:
                                standard = report_row['consumption']['standard_mileage'] = \
                                    report_row['consumption']['standard_worktime'] = \
                                    float(data[4].split(' ')[0]) if data[4] else 0.0
                            except ValueError:
                                standard = report_row['consumption']['standard_mileage'] = \
                                    report_row['consumption']['standard_worktime'] = 0

                            extra_standard = extra_device_standards.get(key, 0.0)
                            if extra_standard:
                                motohours = parse_timedelta(data[2]).seconds / (60.0 * 60.0)
                                extra_standard *= motohours

                                report_row['consumption']['standard_extra_device'] = extra_standard

                            fact = report_row['consumption']['fact'] = \
                                (float(data[3].split(' ')[0]) if data[3] else 0.0) + extra_standard

                            if standard and fact / standard > (1.0 + self.OVERSPANDING_COEFF):
                                report_row['overspanding'] = ((fact / standard) - 1.0) * 100.0
                                overspanding_total += fact - standard

        kwargs.update(
            report_data=report_data,
            today=date.today(),
            discharge_total=discharge_total,
            overspanding_count=overspanding_count,
            overspanding_total=overspanding_total
        )

        return kwargs
