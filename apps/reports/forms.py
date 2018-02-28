# -*- coding: utf-8 -*-
from django import forms

from django.utils.translation import ugettext_lazy as _


class FuelDischargeForm(forms.Form):
    """Форма отчета "Слив топлива" """
    dt_from = forms.DateTimeField(label=_('С'))
    dt_to = forms.DateTimeField(label=_('По'))


class DrivingStyleForm(forms.Form):
    """Форма отчета "Стиль вождения" """
    dt_from = forms.DateTimeField(label=_('С'))
    dt_to = forms.DateTimeField(label=_('По'))


class FinishedJobsForm(forms.Form):
    """Форма отчета Актуальность шаблонов заданий" """
    dt_from = forms.DateTimeField(label=_('С'))
    dt_to = forms.DateTimeField(label=_('По'))
    non_actual_param = forms.IntegerField(
        label=_('Условие неактуальности, %'), min_value=1, max_value=99, initial=20, required=True
    )
