import datetime
from collections import OrderedDict

from base.exceptions import ReportException
from reports import forms
from reports.utils import local_to_utc_time
from reports.views.base import BaseVchmReportView, WIALON_NOT_LOGINED, WIALON_USER_NOT_FOUND
from users.models import User
from wialon.api import get_units
from wialon.exceptions import WialonException


class VchmTixiingView(BaseVchmReportView):
    """Суточный отчет для таксировки ПЛ"""
    form_class = forms.VchmTixiingForm
    template_name = 'reports/vchm_taxiing.html'
    report_name = 'Суточный отчет для таксировки ПЛ'
    xls_heading_merge = 7

    def get_default_form(self):
        data = self.request.POST if self.request.method == 'POST' else {
            'dt_from': datetime.date.today() - datetime.timedelta(days=1),
            'dt_to': datetime.date.today() - datetime.timedelta(days=1)
        }
        return self.form_class(data)

    def get_context_data(self, **kwargs):
        kwargs = super(VchmTixiingView, self).get_context_data(**kwargs)
        report_data = None
        form = kwargs['form']

        sess_id = self.request.session.get('sid')
        if not sess_id:
            raise ReportException(WIALON_NOT_LOGINED)

        try:
            units_list = get_units(sess_id=sess_id, extra_fields=True)
        except WialonException as e:
            raise ReportException(str(e))

        kwargs['units'] = units_list

        if self.request.POST:

            if form.is_valid():
                report_data = OrderedDict()

                user = User.objects.filter(is_active=True) \
                    .filter(wialon_username=self.request.session.get('user')).first()
                if not user:
                    raise ReportException(WIALON_USER_NOT_FOUND)

                dt_from = local_to_utc_time(datetime.datetime.combine(
                    form.cleaned_data['dt_from'],
                    datetime.time(0, 0, 0)
                ), user.wialon_tz)
                dt_to = local_to_utc_time(datetime.datetime.combine(
                    form.cleaned_data['dt_to'],
                    datetime.time(23, 59, 59)
                ), user.wialon_tz)

            kwargs.update(
                report_data=report_data,
            )

        return kwargs

    def write_xls_data(self, worksheet, context):
        worksheet = super(VchmTixiingView, self).write_xls_data(worksheet, context)

        for col in range(8):
            worksheet.col(col).width = 5000
        worksheet.col(3).width = 12000

        # header
        worksheet.write_merge(1, 1, 0, 7, 'В процессе реализации')

        return worksheet
