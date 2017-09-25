# -*- coding: utf-8 -*-
from django import forms

from django.utils.translation import ugettext_lazy as _
from users.models import User


class BaseReportForm(forms.Form):
    dt_from = forms.DateTimeField(label=_('С'))
    dt_to = forms.DateTimeField(label=_('По'))
    sid = forms.CharField(widget=forms.HiddenInput)
    user = forms.ModelChoiceField(
        queryset=User.objects.filter(is_active=True), to_field_name='username',
        widget=forms.HiddenInput
    )


class FuelDischargeForm(BaseReportForm):
    """Форма отчета "Слив топлива" """
    pass


class DrivingStyleForm(BaseReportForm):
    """Форма отчета "Стиль вождения" """
    pass
