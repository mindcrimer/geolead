# -*- coding: utf-8 -*-
from collections import OrderedDict
from datetime import date, timedelta
import json
import time

from django.conf import settings
from django.utils.timezone import utc

import requests

from reports import forms
from reports.jinjaglobals import render_background
from reports.utils import get_drivers_fio
from reports.views.base import BaseReportView, ReportException, WIALON_INTERNAL_EXCEPTION
from ura.wialon.api import get_units_list
from ura.wialon.auth import authenticate_at_wialon


class DrivingStyleView(BaseReportView):
    """Стиль вождения"""
    form = forms.DrivingStyleForm
    template_name = 'reports/driving_style.html'

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
        delta = timedelta(seconds=0)
        parts = value.split(' ')
        digits = 0

        for part in parts:

            if part.isdigit():
                digits = int(part)
                continue

            if ':' in part:
                hours, minutes, seconds = [int(x) for x in part.split(':')]
                delta += timedelta(seconds=((hours * 3600) + (minutes * 60) + seconds))

            elif 'day' in part:
                delta += timedelta(days=digits)

            elif 'week' in part:
                delta += timedelta(days=digits * 7)

            elif 'month' in part:
                delta += timedelta(days=digits * 30)

            elif 'year' in part:
                delta += timedelta(days=digits * 365)

        return delta

    def get_context_data(self, **kwargs):
        kwargs = super(DrivingStyleView, self).get_context_data(**kwargs)
        report_data = None
        form = kwargs['form']
        kwargs['today'] = date.today()

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
                                        'itemId': 15828651,
                                        'col': ['7'],
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
                            'reportResourceId': 15828651,
                            'reportTemplateId': 7,
                            'reportTemplate': None,
                            'reportObjectId': 15932813,
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
                            details = row['r']
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

                            for subject in details:
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
                                    report_row['facts'][viol_key]['count'] += 1
                                    report_row['facts'][viol_key]['seconds'] += (
                                        subject['t2'] - subject['t1']
                                    )

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
