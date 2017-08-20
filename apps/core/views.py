# -*- coding: utf-8 -*-
import json
import time
from collections import OrderedDict
from datetime import timedelta, datetime, date

from django.conf import settings
from django.utils.timezone import utc

import requests

from core import forms
from snippets.utils.datetime import utcnow
from snippets.views import BaseTemplateView


OVERSPANDING_COEFF = 0.05


class HomeView(BaseTemplateView):
    template_name = 'core/home.html'


class OverSpandingView(BaseTemplateView):
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

                requests.post(
                    settings.WIALON_BASE_URL + '?svc=core/batch&sid=' + sess_id, {
                        'params': json.dumps({
                            "params": [
                                {
                                    "svc": "report/cleanup_result",
                                    "params": {}
                                },
                                {
                                    "svc": "report/get_report_data",
                                    "params": {
                                        "itemId": 14175015,
                                        "col": ["3"],
                                        "flags": 0
                                    }
                                }
                            ],
                            "flags": 0
                        }),
                        'sid': sess_id
                    }
                )

                r = requests.post(
                    settings.WIALON_BASE_URL + '?svc=report/exec_report&sid=' + sess_id, {
                        'params': json.dumps({
                            "reportResourceId": 14175015,
                            "reportTemplateId": 3,
                            "reportTemplate": None,
                            "reportObjectId": 15826705,
                            "reportObjectSecId": 0,
                            "interval": {
                                "flags": 0,
                                "from": dt_from,
                                "to": dt_to
                            }
                        }),
                        'sid': sess_id
                    }
                )

                res = r.json()
                for index, table in enumerate(res['reportResult']['tables']):
                    rows = requests.post(
                        settings.WIALON_BASE_URL + '?svc=report/select_result_rows&sid=' +
                        sess_id, {
                            'params': json.dumps({
                                "tableIndex": index,
                                "config": {
                                    "type": "range",
                                    "data": {
                                        "from": 0,
                                        "to": table['rows'] - 1,
                                        "level": 0
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
                                res['reportResult']['stats'][0][1],
                                res['reportResult']['stats'][1][1]
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
                                overspanding_total += float(data[3].split(' ')[0])

                            if data[4]:
                                overspanding_count += int(data[4])

                        elif table['name'] == 'unit_group_generic':
                            standard = report_row['consumption']['standard_mileage'] = \
                                report_row['consumption']['standard_worktime'] = \
                                float(data[4].split(' ')[0]) if data[4] else 0

                            fact = report_row['consumption']['fact'] = \
                                float(data[3].split(' ')[0]) if data[3] else 0

                            if standard and fact / standard > (1.0 + OVERSPANDING_COEFF):
                                report_row['overspanding'] = '%s л' % (fact - standard)
                                overspanding_total += (fact - standard)

        else:
            form = forms.FuelDischargeForm({
                'dt_from': utcnow() - timedelta(seconds=60 * 60),
                'dt_to': utcnow()
            })

            form.is_valid()

        kwargs.update(
            form=form,
            report_data=report_data,
            today=date.today(),
            overspanding_count=overspanding_count,
            overspanding_total=overspanding_total
        )

        return kwargs

    def post(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        return self.render_to_response(context)
