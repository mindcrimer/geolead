# -*- coding: utf-8 -*-
from collections import OrderedDict
import datetime

from django.utils.timezone import utc

from base.exceptions import ReportException
from reports import forms
from reports.jinjaglobals import render_background
from reports.utils import get_period, get_drivers_fio, utc_to_local_time, geocode
from reports.views.base import BaseReportView, WIALON_NOT_LOGINED, WIALON_USER_NOT_FOUND
from ura import FUEL_SENSOR_PREFIXES
from users.models import User
from wialon.api import get_messages, get_units
from wialon.exceptions import WialonException


class FaultsView(BaseReportView):
    """Отчет по неисправностям"""
    form = forms.FaultsForm
    template_name = 'reports/faults.html'
    report_name = 'Отчет по неисправностям'

    def get_default_form(self):
        data = self.request.POST if self.request.method == 'POST' else {
            'dt': datetime.datetime.now().replace(hour=0, minute=0, second=0, tzinfo=utc),
            'job_extra_period': 2
        }
        return self.form(data)

    @staticmethod
    def get_new_grouping():
        return {
            'key': '',
            'place': '',
            'dt': '',
            'driver_name': '',
            'faults': []
        }

    def get_context_data(self, **kwargs):
        kwargs = super(FaultsView, self).get_context_data(**kwargs)
        report_data = None
        form = kwargs['form']
        kwargs['today'] = datetime.date.today()
        stats = {
            'total': 0,
            'broken': 0,
        }

        if self.request.POST:
            report_data = OrderedDict()

            if form.is_valid():
                sess_id = self.request.session.get('sid')
                if not sess_id:
                    raise ReportException(WIALON_NOT_LOGINED)

                user = User.objects.filter(is_active=True) \
                    .filter(wialon_username=self.request.session.get('user')).first()

                if not user:
                    raise ReportException(WIALON_USER_NOT_FOUND)

                report_date = form.cleaned_data['dt']

                dt_from = datetime.datetime.combine(
                    report_date, datetime.time(0, 0, 0)
                ).replace(tzinfo=user.wialon_tz)
                dt_to = datetime.datetime.combine(
                    report_date, datetime.time(23, 59, 59)
                ).replace(tzinfo=user.wialon_tz)

                dt_from, dt_to = get_period(
                    dt_from,
                    dt_to,
                    user.wialon_tz
                )

                units_list = get_units(sess_id=sess_id)
                stats['total'] = len(units_list)

                for i, unit in enumerate(units_list):
                    print(i, unit['name'])
                    unit_id = unit['id']
                    report_row = self.get_new_grouping()
                    report_data[unit_id] = report_row

                    report_row['key'] = unit['name']
                    report_row['driver_name'] = get_drivers_fio(
                        units_list,
                        unit['name'],
                        form.cleaned_data['dt_from'],
                        form.cleaned_data['dt_to'],
                        user.ura_tz
                    ) or ''

                    try:
                        messages = tuple(filter(
                            lambda x: x['p'].get('odometer') is None
                            and x['p'].get('moto') is None,
                            get_messages(unit['id'], dt_from, dt_to, sess_id=sess_id)['messages']
                        ))
                    except WialonException as e:
                        raise ReportException(str(e))

                    messages = tuple(reversed(messages))[:1]
                    if not messages:
                        report_row['faults'].append('нет данных за выбранный интервал')
                    else:
                        message = messages[0]

                        if message.get('pos'):
                            report_row['place'] = geocode(
                                message['pos']['y'], message['pos']['x']
                            ) or ''

                        report_row['dt'] = utc_to_local_time(
                            datetime.datetime.utcfromtimestamp(message['t']),
                            user.wialon_tz
                        ) or ''

                        params = message['p']
                        pwr_ext = params.get('pwr_ext')
                        hdop = params.get('hdop')

                        if pwr_ext is None:
                            report_row['faults'].append(
                                'отсутствуют данные о внешнем питании'
                            )

                        elif pwr_ext < 10:
                            report_row['faults'].append('отсутствует внешнее питание')

                        if hdop is None:
                            report_row['faults'].append(
                                'отсутствуют данные о Глонасс модуле'
                            )
                        elif params.get('hdop', 100) > 1:
                            report_row['faults'].append('неисправность Глонасс модуля')

                        fuel_levels = tuple(filter(
                            lambda x: any(
                                [x[0].startswith(f) for f in FUEL_SENSOR_PREFIXES]
                            ) and x[1] is not None,
                            params.items()
                        ))

                        if not fuel_levels:
                            report_row['faults'].append('отсутствуют данные о ДУТ')
                        else:
                            for param, value in fuel_levels:
                                if value is not None and not 1 < value < 4096:
                                    report_row['faults'].append('неисправность ДУТ')
                                    break

                    if report_row['faults']:
                        stats['broken'] += 1

        kwargs.update(
            stats=stats,
            report_data=report_data,
            render_background=render_background
        )

        return kwargs
