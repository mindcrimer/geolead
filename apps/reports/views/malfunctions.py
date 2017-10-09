# -*- coding: utf-8 -*-
from collections import OrderedDict
import datetime

from base.exceptions import ReportException
from reports import forms
from reports.jinjaglobals import render_background
from reports.utils import get_period
from reports.views.base import BaseReportView, WIALON_NOT_LOGINED, WIALON_USER_NOT_FOUND
from ura.wialon.api import get_messages
from ura.wialon.exceptions import WialonException


class MalfunctionsView(BaseReportView):
    """Отчет по неисправностям"""
    form = forms.DrivingStyleForm
    template_name = 'reports/malfunctions.html'
    report_name = 'Отчет по неисправностям'

    @staticmethod
    def get_new_grouping():
        return {
        }

    def get_context_data(self, **kwargs):
        kwargs = super(MalfunctionsView, self).get_context_data(**kwargs)
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

                dt_from, dt_to = get_period(
                    form.cleaned_data['dt_from'],
                    form.cleaned_data['dt_to'],
                    user.wialon_tz
                )

                try:
                    messages = get_messages(15840462, dt_from, dt_to, sess_id=sess_id)
                except WialonException as e:
                    raise ReportException(str(e))

                a = 1

        kwargs.update(
            report_data=report_data,
            render_background=render_background
        )

        return kwargs
