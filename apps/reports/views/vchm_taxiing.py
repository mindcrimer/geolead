import datetime
from collections import OrderedDict

from base.exceptions import ReportException
from moving.service import MovingService
from reports import forms
from reports.views.base import BaseVchmReportView, WIALON_NOT_LOGINED, WIALON_USER_NOT_FOUND
from users.models import User
from wialon.api import get_units
from wialon.exceptions import WialonException


class VchmTaxiingView(BaseVchmReportView):
    """Суточный отчет для таксировки ПЛ"""
    form_class = forms.VchmTaxiingForm
    template_name = 'reports/vchm_taxiing.html'
    report_name = 'Суточный отчет для таксировки ПЛ'
    xls_heading_merge = 7

    def __init__(self, *args, **kwargs):
        super(VchmTaxiingView).__init__(*args, **kwargs)
        self.units_dict = {}

    def get_default_form(self):
        data = self.request.POST if self.request.method == 'POST' else {
            'dt_from': datetime.date.today() - datetime.timedelta(days=1),
            'dt_to': datetime.date.today() - datetime.timedelta(days=1)
        }
        return self.form_class(data)

    def get_context_data(self, **kwargs):
        kwargs = super(VchmTaxiingView, self).get_context_data(**kwargs)
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
                report_data = []

                user = User.objects.filter(is_active=True) \
                    .filter(wialon_username=self.request.session.get('user')).first()
                if not user:
                    raise ReportException(WIALON_USER_NOT_FOUND)

                local_dt_from = datetime.datetime.combine(
                    form.cleaned_data['dt_from'],
                    datetime.time(0, 0, 0)
                )
                local_dt_to = datetime.datetime.combine(
                    form.cleaned_data['dt_to'],
                    datetime.time(23, 59, 59)
                )

                selected_unit = form.cleaned_data.get('unit')
                self.units_dict = OrderedDict(
                    (x['name'], x) for x in units_list
                    if not selected_unit or (selected_unit and x['id'] == selected_unit)
                )

                service = MovingService(
                    user,
                    local_dt_from,
                    local_dt_to,
                    object_id=selected_unit if selected_unit else None,
                    sess_id=sess_id,
                    units_dict=self.units_dict
                )
                service.exec_report()
                service.analyze()

            kwargs.update(
                report_data=report_data,
            )

        return kwargs

    def write_xls_data(self, worksheet, context):
        worksheet = super(VchmTaxiingView, self).write_xls_data(worksheet, context)

        for col in range(8):
            worksheet.col(col).width = 5000
        worksheet.col(3).width = 12000

        # header
        worksheet.write_merge(1, 1, 0, 7, 'В процессе реализации')

        return worksheet
