# -*- coding: utf-8 -*-
import json
import time
from collections import OrderedDict
from datetime import timedelta, datetime, date

from core.jinjaglobals import render_background
from django.conf import settings
from django.utils.timezone import utc

import requests

from core import forms
from snippets.utils.datetime import utcnow
from snippets.views import BaseTemplateView


OVERSPANDING_COEFF = 0.05


class HomeView(BaseTemplateView):
    """Главная страница"""
    template_name = 'core/home.html'


class BaseReportView(BaseTemplateView):
    """Базовый класс отчета"""
    def post(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        return self.render_to_response(context)


class DrivingStyleView(BaseReportView):
    """Стиль вождения"""
    template_name = 'core/driving_style.html'

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
            'rating': 100.0
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
        report_data = OrderedDict()
        kwargs['today'] = date.today()

        if kwargs['view'].request.POST:
            form = forms.DrivingStyleForm(kwargs['view'].request.POST)
            if form.is_valid():
                # получение сессии:
                r = requests.get(
                    settings.WIALON_BASE_URL + '?svc=token/login&params={%22token%22:%22' +
                    settings.WIALON_TOKEN + '%22}'
                )
                res = r.json()
                sess_id = res['eid']

                dt_from = form.cleaned_data['dt_from'].replace(tzinfo=utc)
                dt_to = form.cleaned_data['dt_to'].replace(tzinfo=utc)

                dt_from = int(time.mktime(dt_from.timetuple()))
                dt_to = int(time.mktime(dt_to.timetuple()))

                res = requests.post(
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

                r = res.json()
                print(r)

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
                print(r)

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

                        for row in rows:
                            data = row['c']
                            details = row['r']
                            key = (data[0], data[1])

                            if key not in report_data:
                                report_data[key] = self.get_new_grouping()

                            report_row = report_data[key]
                            report_row['total_time'] = \
                                self.parse_time_delta(data[5]).seconds \
                                + (self.parse_time_delta(data[5]).days * 3600 * 24)

                            for subject in details:
                                violation = subject['c'][3]
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

        else:
            form = forms.FuelDischargeForm({
                'dt_from': utcnow().replace(hour=0, minute=0, second=0),
                'dt_to': utcnow().replace(hour=23, minute=59, second=59)
            })

            form.is_valid()

        kwargs.update(
            form=form,
            report_data=report_data,
            render_background=render_background
        )

        return kwargs


class OverSpandingView(BaseReportView):
    """Перерасход топлива"""
    template_name = 'core/over_spanding.html'

    @staticmethod
    def get_new_grouping():
        return {
            'plan_worktime': ('', ''),
            'driver_name': '',
            'discharge': {
                'place': '',
                'dt': ''
            },
            'consumption': {
                'standard_mileage': '',
                'standard_worktime': '',
                'fact': ''
            },
            'overspanding': ''
        }

    def get_context_data(self, **kwargs):
        kwargs = super(OverSpandingView, self).get_context_data(**kwargs)
        report_data = OrderedDict()
        overspanding_total = .0
        discharge_total = .0
        overspanding_count = 0

        if kwargs['view'].request.POST:
            form = forms.FuelDischargeForm(kwargs['view'].request.POST)
            if form.is_valid():
                # получение сессии:
                r = requests.get(
                    settings.WIALON_BASE_URL + '?svc=token/login&params={%22token%22:%22' +
                    settings.WIALON_TOKEN + '%22}'
                )
                res = r.json()
                sess_id = res['eid']

                dt_from = form.cleaned_data['dt_from'].replace(tzinfo=utc)
                dt_to = form.cleaned_data['dt_to'].replace(tzinfo=utc)

                dt_from = int(time.mktime(dt_from.timetuple()))
                dt_to = int(time.mktime(dt_to.timetuple()))

                res = requests.post(
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

                r = res.json()
                print(r)

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
                print(r)

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
                                        'level': 0
                                    }
                                }
                            }),
                            'sid': sess_id
                        }
                    ).json()

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

                        if table['name'] == 'unit_group_trips':
                            report_row['driver_name'] = data[4]

                        elif table['name'] == 'unit_group_thefts':
                            report_row['discharge']['place'] = data[1]['t'] \
                                if data[1] and isinstance(data[1], dict) else ''

                            report_row['discharge']['dt'] = data[2]['t'] \
                                if data[2] and isinstance(data[2], dict) else ''

                            if len(data[3].replace('-', '')) > 0:
                                discharge_total += float(data[3].split(' ')[0])

                            if data[4]:
                                overspanding_count += int(data[4])

                        elif table['name'] == 'unit_group_generic':
                            standard = report_row['consumption']['standard_mileage'] = \
                                report_row['consumption']['standard_worktime'] = \
                                float(data[4].split(' ')[0]) if data[4] else 0

                            fact = report_row['consumption']['fact'] = \
                                float(data[3].split(' ')[0]) if data[3] else 0

                            if standard and fact / standard > (1.0 + OVERSPANDING_COEFF):
                                report_row['overspanding'] = fact - standard
                                overspanding_total += fact - standard

        else:
            form = forms.FuelDischargeForm({
                'dt_from': utcnow().replace(hour=0, minute=0, second=0),
                'dt_to': utcnow().replace(hour=23, minute=59, second=59)
            })

            form.is_valid()

        kwargs.update(
            form=form,
            report_data=report_data,
            today=date.today(),
            discharge_total=discharge_total,
            overspanding_count=overspanding_count,
            overspanding_total=overspanding_total
        )

        return kwargs
