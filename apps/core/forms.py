# -*- coding: utf-8 -*-
from django import forms

from django.utils.translation import ugettext_lazy as _


class FuelDischargeForm(forms.Form):
    """Форма отчета "Слив топлива" """
    dt_from = forms.DateTimeField(label=_('С'))
    dt_to = forms.DateTimeField(label=_('По'))
