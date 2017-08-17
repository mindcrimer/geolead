# -*- coding: utf-8 -*-
import json
import time
import urllib
from datetime import timedelta

import requests

from core import forms
from django.conf import settings
from snippets.utils.datetime import utcnow
from snippets.views import BaseTemplateView


class HomeView(BaseTemplateView):
    template_name = 'core/home.html'

    def get_context_data(self, **kwargs):
        kwargs = super(HomeView, self).get_context_data(**kwargs)
        report_data = []

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

                dt_from = int(time.mktime(form.cleaned_data['dt_from'].timetuple()))
                dt_to = int(time.mktime(form.cleaned_data['dt_to'].timetuple()))

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
                    )

                    report_data.append({
                        'meta': table,
                        'rows': rows.json()
                    })

        else:
            form = forms.FuelDischargeForm({
                'dt_from': utcnow() - timedelta(seconds=60 * 60),
                'dt_to': utcnow()
            })

            form.is_valid()
            kwargs['form'] = form

        kwargs['report_data'] = report_data

        return kwargs

    def post(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        return self.render_to_response(context)
