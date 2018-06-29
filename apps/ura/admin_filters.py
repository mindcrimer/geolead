from django.contrib.admin.filters import SimpleListFilter
from django.utils.translation import ugettext_lazy as _


class NullFilterSpec(SimpleListFilter):
    title = ''

    parameter_name = ''

    def lookups(self, request, model_admin):
        return (
            ('1', _('Есть значение'), ),
            ('0', _('Нет значения'), ),
        )

    def queryset(self, request, queryset):

        if self.value() == '0':
            return queryset.filter(**{'%s__isnull' % self.parameter_name: True})

        if self.value() == '1':
            return queryset.filter(**{'%s__isnull' % self.parameter_name: False})

        return queryset


class MileageStandardFilterSpec(NullFilterSpec):
    title = 'Норматив пробега, км'
    parameter_name = 'mileage_standard'


class ParkingTimeStandardFilterSpec(NullFilterSpec):
    title = 'Норматив времени стоянок, мин.'
    parameter_name = 'parking_time_standard'


class PointsMileageStandardFilterSpec(NullFilterSpec):
    title = 'Норматив пробега, км'
    parameter_name = 'points__mileage_standard'


class PointsParkingTimeStandardFilterSpec(NullFilterSpec):
    title = 'Норматив времени стоянок, мин.'
    parameter_name = 'points__parking_time_standard'


class PointsTotalTimeStandardFilterSpec(NullFilterSpec):
    title = 'Норматив времени нахождения, мин.'
    parameter_name = 'points__total_time_standard'


class SpaceOverstatementsStandardNullFilterSpec(NullFilterSpec):
    title = 'Норматив перенахождения вне плановых геозон, мин.'
    parameter_name = 'space_overstatements_standard'


class TotalTimeStandardFilterSpec(NullFilterSpec):
    title = 'Норматив времени нахождения, мин.'
    parameter_name = 'total_time_standard'
