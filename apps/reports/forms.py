from django import forms
from django.utils.translation import ugettext_lazy as _

from reports import DEFAULT_TOTAL_TIME_STANDARD_MINUTES, \
    DEFAULT_OVERSTATEMENT_NORMAL_PERCENTAGE, DEFAULT_OVERSPANDING_NORMAL_PERCENTAGE


class DrivingStyleForm(forms.Form):
    """Форма отчета "Стиль вождения" """
    dt_from = forms.DateTimeField(label=_('С'))
    dt_to = forms.DateTimeField(label=_('По'))
    unit = forms.IntegerField(required=False, label=_('Объект'))
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
    include_details = forms.BooleanField(
        label=_('Детализация'), initial=True, widget=forms.CheckboxInput, required=False
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
    unit = forms.IntegerField(required=False, label=_('Объект'))
    overspanding_percentage = forms.IntegerField(
        label=_('Показатель превышения фактического расхода топлива на нормативы, %'),
        min_value=0, max_value=1000, initial=DEFAULT_OVERSPANDING_NORMAL_PERCENTAGE, required=True
    )


class InvalidJobStartEndForm(forms.Form):
    """Форма отчета о несвоевременном начале и окончании выполнения задания" """
    dt_from = forms.DateTimeField(label=_('С'))
    dt_to = forms.DateTimeField(label=_('По'))
    include_fixed = forms.BooleanField(
        label=_('Включить фиксированные задания'), initial=False, widget=forms.CheckboxInput,
        required=False
    )
    job_end_timeout = forms.IntegerField(
        max_value=300, min_value=0,
        label=_('Максимальная продолжительность отсутствия объекта в месте окончания смены'),
        initial=30
    )


class OverstatementsForm(forms.Form):
    """Форма отчета о сверхнормативных простоях"""
    dt_from = forms.DateTimeField(label=_('С'))
    dt_to = forms.DateTimeField(label=_('По'))
    overstatement_param = forms.IntegerField(
        label=_('Условие превышения над нормативным временем, перенахождения / перепростоя, %'),
        min_value=0, max_value=99, initial=DEFAULT_OVERSTATEMENT_NORMAL_PERCENTAGE, required=True
    )


class VchmDrivingStyleForm(forms.Form):
    """Форма отчета по БДД (ВЧМ)"""
    dt_from = forms.DateField(label=_('С'))
    dt_to = forms.DateField(label=_('По'))
    unit = forms.IntegerField(required=False, label=_('Объект'))


class VchmIdleTimesForm(forms.Form):
    """Форма отчета по простоям за смену"""
    dt_from = forms.DateField(label=_('С'))
    dt_to = forms.DateField(label=_('По'))
    unit = forms.IntegerField(required=False, label=_('Объект'))
    default_space_time_standard = forms.FloatField(
        label=_(
            'Норматив нахождения в неизвестных геозонах (минут), '
            'если не указано в таблице нормативов'
        ),
        min_value=0, max_value=10000, initial=DEFAULT_TOTAL_TIME_STANDARD_MINUTES, required=True
    )
    overstatement_param = forms.IntegerField(
        label=_('Условие превышения над нормативным временем, перенахождения / перепростоя, %'),
        min_value=0, max_value=99, initial=DEFAULT_OVERSTATEMENT_NORMAL_PERCENTAGE, required=True
    )


class VchmTaxiingForm(forms.Form):
    """Форма cуточного отчета для таксировки ПЛ"""
    dt = forms.DateField(label=_('По'))
    unit = forms.IntegerField(required=True, label=_('Объект'))
    overstatement_param = forms.IntegerField(
        label=_('Условие превышения над нормативным временем, перенахождения / перепростоя, %'),
        min_value=0, max_value=99, initial=DEFAULT_OVERSTATEMENT_NORMAL_PERCENTAGE, required=True
    )
