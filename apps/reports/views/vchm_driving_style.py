import datetime

from django.utils.timezone import utc

from reports import forms
from reports.views.base import BaseVchmReportView


class VchmDrivingStyleView(BaseVchmReportView):
    """Отчет по БДД (ВЧМ)"""
    form_class = forms.VchmDrivingStyleForm
    template_name = 'reports/vchm_driving_style.html'
    report_name = 'Отчет по БДД (ВЧМ)'
    xls_heading_merge = 7

    def get_default_form(self):
        data = self.request.POST if self.request.method == 'POST' else {
            'dt_from': datetime.datetime.now().replace(hour=0, minute=0, second=0, tzinfo=utc),
            'dt_to': datetime.datetime.now().replace(hour=23, minute=59, second=59, tzinfo=utc)
        }
        return self.form_class(data)

    def get_context_data(self, **kwargs):
        kwargs = super(VchmDrivingStyleView, self).get_context_data(**kwargs)
        report_data = None
        form = kwargs['form']

        return kwargs

    def write_xls_data(self, worksheet, context):
        worksheet = super(VchmDrivingStyleView, self).write_xls_data(worksheet, context)

        for col in range(8):
            worksheet.col(col).width = 5000
        worksheet.col(3).width = 12000

        # header
        worksheet.write_merge(1, 1, 0, 7, 'В процессе реализации')

        return worksheet
