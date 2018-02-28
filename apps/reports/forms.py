# -*- coding: utf-8 -*-
from django import forms

from django.utils.translation import ugettext_lazy as _


class DrivingStyleForm(forms.Form):
    """Форма отчета "Стиль вождения" """
    dt_from = forms.DateTimeField(label=_('С'))
    dt_to = forms.DateTimeField(label=_('По'))


class FaultsForm(forms.Form):
    """Форма отчета о состоянии оборудования ССМТ"""
    dt = forms.DateField(label=_('На дату'))
    job_extra_period = forms.IntegerField(
        label=_('Дополнительное время до и после ПЛ, ч'), min_value=0, max_value=99,
        initial=2, required=True
    )


class FinishedJobsForm(forms.Form):
    """Форма отчета Актуальность шаблонов заданий" """
    dt_from = forms.DateTimeField(label=_('С'))
    dt_to = forms.DateTimeField(label=_('По'))
    non_actual_param = forms.IntegerField(
        label=_('Условие неактуальности, %'), min_value=1, max_value=99, initial=20, required=True
    )


class FuelDischargeForm(forms.Form):
    """Форма отчета "Слив топлива" """
    dt_from = forms.DateTimeField(label=_('С'))
    dt_to = forms.DateTimeField(label=_('По'))


class InvalidJobStartEndForm(forms.Form):
    """Форма отчета о несвоевременном начале и окончании выполнения задания" """
    dt_from = forms.DateTimeField(label=_('С'))
    dt_to = forms.DateTimeField(label=_('По'))


class OverstatementsForm(forms.Form):
    """Форма отчета о сверхнормативных простоях"""
    dt_from = forms.DateTimeField(label=_('С'))
    dt_to = forms.DateTimeField(label=_('По'))
