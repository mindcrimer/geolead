# -*- coding: utf-8 -*-
from collections import OrderedDict
import datetime

from base.exceptions import ReportException
from reports import forms
from reports.utils import get_period
from reports.views.base import BaseReportView, WIALON_NOT_LOGINED, WIALON_USER_NOT_FOUND
from users.models import User


class FinishedJobsView(BaseReportView):
    """Отчет по актуальности шаблонов заданий"""
    form = forms.DrivingStyleForm
    template_name = 'reports/finished_jobs.html'
    report_name = 'Отчет по актуальности шаблонов заданий'

    @staticmethod
    def get_new_grouping():
        return {
            'key': '',
            'place': '',
            'dt': ''
        }

    def get_context_data(self, **kwargs):
        kwargs = super(FinishedJobsView, self).get_context_data(**kwargs)
        report_data = None
        form = kwargs['form']
        kwargs['today'] = datetime.date.today()
        stats = {
            'total': 0,
            'non_actual': 0
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

                dt_from, dt_to = get_period(
                    form.cleaned_data['dt_from'],
                    form.cleaned_data['dt_to'],
                    user.wialon_tz
                )

        kwargs.update(
            stats=stats,
            report_data=report_data
        )

        return kwargs
