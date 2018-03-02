# -*- coding: utf-8 -*-
from django import forms

from django.utils.translation import ugettext_lazy as _


class DrivingStyleForm(forms.Form):
    """Форма отчета "Стиль вождения" """
    dt_from = forms.DateTimeField(label=_('С'))
    dt_to = forms.DateTimeField(label=_('По'))
    normal_rating = forms.IntegerField(
        label=_('Процент нарушений, при котором требуется профилактическая беседа'), min_value=0,
        max_value=99, initial=10, required=True
    )
    bad_rating = forms.IntegerField(
        label=_(
            'Процент нарушений, при котором требуется профилактическая беседа '
            'с возможным лишением части премии'
        ), min_value=0, max_value=99, initial=30, required=True
    )

    def clean(self):
        cleaned_data = self.cleaned_data
        if cleaned_data.get('bad_rating', 0) <= cleaned_data.get('normal_rating', 0):
            self.add_error(
                'bad_rating',
                'Рейтинг с возможностью лишения премии должен быть выше '
                'рейтинга, при котором требуется только профилактическая беседа'
            )
        return cleaned_data


class FaultsForm(forms.Form):
    """Форма отчета о состоянии оборудования ССМТ"""
    dt = forms.DateField(label=_('На дату'))
    job_extra_offset = forms.IntegerField(
        label=_('Дополнительное время до и после ПЛ, ч'), min_value=0, max_value=99,
        initial=2, required=True
    )


class FinishedJobsForm(forms.Form):
    """Форма отчета Актуальность шаблонов заданий" """
    dt_from = forms.DateTimeField(label=_('С'))
    dt_to = forms.DateTimeField(label=_('По'))
    non_actual_param = forms.IntegerField(
        label=_('Условие неактуальности, %'), min_value=0, max_value=99, initial=20, required=True
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
