# -*- coding: utf-8 -*-
from django import forms

from django.utils.translation import ugettext_lazy as _


class BaseReportForm(forms.Form):
    dt_from = forms.DateTimeField(label=_('С'))
    dt_to = forms.DateTimeField(label=_('По'))


class FuelDischargeForm(BaseReportForm):
    """Форма отчета "Слив топлива" """
    pass


class DrivingStyleForm(BaseReportForm):
    """Форма отчета "Стиль вождения" """
    pass
