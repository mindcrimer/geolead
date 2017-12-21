# -*- coding: utf-8 -*-
from django.contrib import admin
from django.contrib.admin import TabularInline
from django.contrib.admin.filters import SimpleListFilter
from django.utils.translation import ugettext_lazy as _
from import_export.admin import ExportMixin

from ura import models, import_export


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


class SpaceOverstatementsStandardNullFilterSpec(NullFilterSpec):
    title = 'Норматив перепростоя вне плановых геозон, мин.'
    parameter_name = 'space_overstatements_standard'


class PointsTotalTimeStandardFilterSpec(NullFilterSpec):
    title = 'Норматив времени нахождения, мин.'
    parameter_name = 'points__total_time_standard'


class PointsParkingTimeStandardFilterSpec(NullFilterSpec):
    title = 'Норматив времени стоянок, мин.'
    parameter_name = 'points__parking_time_standard'


class TotalTimeStandardFilterSpec(NullFilterSpec):
    title = 'Норматив времени нахождения, мин.'
    parameter_name = 'total_time_standard'


class ParkingTimeStandardFilterSpec(NullFilterSpec):
    title = 'Норматив времени стоянок, мин.'
    parameter_name = 'parking_time_standard'


@admin.register(models.UraJobLog)
class UraJobLogAdmin(admin.ModelAdmin):
    """Лог путевых листов"""
    date_hierarchy = 'created'
    fields = models.UraJobLog().collect_fields()
    list_display = ('id', 'job_id', 'user', 'response_status', 'created')
    list_display_links = ('id', 'job_id')
    list_filter = ('response_status', 'user')
    readonly_fields = ('created', 'updated', 'job', 'request', 'response', 'response_status')
    search_fields = ('=id', '=job__id', 'request', 'response', 'response_status')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(models.UraJob)
class UraJobAdmin(admin.ModelAdmin):
    """Заявки"""
    date_hierarchy = 'date_begin'
    fields = models.UraJob().collect_fields()
    list_display = ('id', 'name', 'driver_fio', 'date_begin', 'date_end')
    list_display_links = ('id', 'name')
    readonly_fields = ('created', 'updated')
    search_fields = ('=id', 'name', 'unit_id', 'route_id', 'driver_id', 'driver_fio')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class StandardPointTabularInline(TabularInline):
    """Нормативы по геозонам"""
    extra = 0
    fields = models.StandardPoint().collect_fields()
    model = models.StandardPoint
    readonly_fields = ('created', 'updated')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(models.StandardPoint)
class StandardPointAdmin(ExportMixin, admin.ModelAdmin):
    """Геозоны"""
    fields = models.StandardPoint().collect_fields()
    list_display = ('id', 'title', 'wialon_id', 'job_template', 'created', 'updated')
    list_display_links = ('id', 'title')
    list_filter = (
        TotalTimeStandardFilterSpec, ParkingTimeStandardFilterSpec, 'job_template__user'
    )
    list_select_related = True
    ordering = ('-created',)
    readonly_fields = ('created', 'updated')
    resource_class = import_export.StandardPointResource
    search_fields = ('=id', '=wialon_id', 'title', 'job_template__title')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(models.StandardJobTemplate)
class StandardJobTemplateAdmin(admin.ModelAdmin):
    """Шаблоны отчетов"""
    date_hierarchy = 'created'
    fields = models.StandardJobTemplate().collect_fields()
    inlines = (StandardPointTabularInline,)
    list_display = (
        'id', 'title', 'wialon_id', 'created', 'updated'
    )
    list_display_links = ('id', 'title')
    list_filter = (
        SpaceOverstatementsStandardNullFilterSpec, PointsTotalTimeStandardFilterSpec,
        PointsParkingTimeStandardFilterSpec, 'user'
    )
    ordering = ('-created',)
    readonly_fields = ('created', 'updated')
    search_fields = ('=id', '=wialon_id', 'title', 'points__title', 'points__wialon_id')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
