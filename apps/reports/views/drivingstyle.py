# -*- coding: utf-8 -*-
from collections import OrderedDict
import datetime
import json
import time

from django.conf import settings

import requests

from reports import forms
from reports.jinjaglobals import render_background
from reports.utils import get_drivers_fio, parse_wialon_report_datetime, \
    get_wialon_driving_style_report_template_id, get_wialon_report_resource_id, \
    get_wialon_report_object_id, local_to_utc_time
from reports.views.base import BaseReportView, ReportException, WIALON_INTERNAL_EXCEPTION, \
    WIALON_NOT_LOGINED, WIALON_USER_NOT_FOUND
from ura.lib.exceptions import APIProcessError
from ura.wialon.api import get_units_list


class DrivingStyleView(BaseReportView):
    """Стиль вождения"""
    form = forms.DrivingStyleForm
    template_name = 'reports/discharge.html'
    report_name = 'Отчет нарушений ПДД и инструкции по эксплуатации техники'

    @staticmethod
    def get_new_grouping():
        return {
            'total_time': .0,
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

            elif 'day' in part:
                delta += datetime.timedelta(days=digits)

            elif 'week' in part:
                delta += datetime.timedelta(days=digits * 7)

            elif 'month' in part:
                delta += datetime.timedelta(days=digits * 30)

            elif 'year' in part:
                delta += datetime.timedelta(days=digits * 365)

        return delta

    def get_context_data(self, **kwargs):
        kwargs = super(DrivingStyleView, self).get_context_data(**kwargs)
        report_data = None
        form = kwargs['form']
        kwargs['today'] = datetime.date.today()

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
                except APIProcessError as e:
                    raise ReportException(str(e))

                dt_from, dt_to = self.get_period(user, form)

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
                                        'itemId': get_wialon_report_resource_id(user),
                                        'col': [
                                            str(get_wialon_driving_style_report_template_id(user))
                                        ],
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
                            'reportResourceId': get_wialon_report_resource_id(user),
                            'reportTemplateId': get_wialon_driving_style_report_template_id(user),
                            'reportTemplate': None,
                            'reportObjectId': get_wialon_report_object_id(user),
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
                    if table['name'] == 'unit_group_ecodriving':
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
                                            'level': 2
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

                            if not data[1]:
                                data[1] = get_drivers_fio(
                                    units_list,
                                    data[0],
                                    form.cleaned_data['dt_from'],
                                    form.cleaned_data['dt_to']
                                ) or ''
                            key = (data[0], data[1])

                            if key not in report_data:
                                report_data[key] = self.get_new_grouping()

                            report_row = report_data[key]
                            report_row['total_time'] = \
                                self.parse_time_delta(data[5]).seconds \
                                + (self.parse_time_delta(data[5]).days * 3600 * 24)

                            details = row['r']

                            for subject in details:

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
                                violation = subject['c'][3].lower() if subject['c'][3] else ''
                                if 'свет' in violation or 'фар' in violation:
                                    viol_key = 'lights'
                                elif 'скорост' in violation or 'превышен' in violation:
                                    viol_key = 'speed'
                                elif 'ремн' in violation or 'ремен' in violation:
                                    viol_key = 'belt'
                                else:
                                    viol_key = ''

                                if viol_key:
                                    delta = subject['t2'] - subject['t1']
                                    report_row['facts'][viol_key]['count'] += 1
                                    report_row['facts'][viol_key]['seconds'] += delta

                                    if detail_data:
                                        # detail_data[viol_key]['count'] = 1
                                        detail_data[viol_key]['seconds'] = delta
                                        detail_data['dt'] = parse_wialon_report_datetime(
                                            subject['c'][9]['t'], user.wialon_tz
                                        )

                                        report_row['details'].append(detail_data)

            for data in report_data.values():
                for viol_key in ('speed', 'lights', 'belt', 'devices'):
                    percentage = data['facts'][viol_key]['seconds'] / data['total_time'] * 100
                    data['percentage'][viol_key] = percentage
                    data['rating'] -= percentage

        kwargs.update(
            report_data=report_data,
            render_background=render_background
        )

        return kwargs
