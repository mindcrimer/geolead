# -*- coding: utf-8 -*-
from django.contrib import admin
from django.contrib.admin import TabularInline
from django.contrib.admin.filters import SimpleListFilter
from django.utils.translation import ugettext_lazy as _

from import_export.admin import ImportExportMixin, ExportMixin

from ura import models, import_export
from ura.enums import JobLogResolution


def approve_logs(modeladmin, request, queryset):
    queryset.update(resolution=JobLogResolution.APPROVED)


approve_logs.short_description = 'Подтвердить исправление'


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
    title = 'Норматив перенахождения вне плановых геозон, мин.'
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


class JobPointInline(admin.TabularInline):
    """Геозоны путевого листа"""
    extra = 0
    fields = models.JobPoint().collect_fields()
    readonly_fields = list(fields)
    readonly_fields.remove('job')
    model = models.JobPoint

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False


@admin.register(models.Job)
class JobAdmin(ExportMixin, admin.ModelAdmin):
    """Путевые листы"""
    date_hierarchy = 'date_begin'
    fields = models.Job().collect_fields()
    inlines = (JobPointInline,)
    list_display = (
        'id', 'name', 'driver_fio', 'route_title', 'unit_title', 'user', 'date_begin', 'date_end'
    )
    list_display_links = ('id', 'name')
    list_filter = ('user',)
    list_select_related = True
    list_per_page = 50
    readonly_fields = ('created', 'updated')
    resource_class = import_export.JobResource
    search_fields = (
        '=id', 'name', 'unit_title', 'driver_fio', 'route_title', 'unit_id', 'route_id',
        'driver_id'
    )

    def get_readonly_fields(self, request, obj=None):
        if request.user.is_superuser:
            return self.readonly_fields

        return self.fields

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(models.JobLog)
class JobLogAdmin(ExportMixin, admin.ModelAdmin):
    """Лог путевых листов"""
    actions = [approve_logs]
    date_hierarchy = 'created'
    fields = models.JobLog().collect_fields()
    list_display = ('id', 'job_id', 'url', 'user', 'resolution', 'response_status', 'created')
    list_display_links = ('id', 'job_id')
    list_filter = ('response_status', 'user', 'resolution')
    list_select_related = False
    list_per_page = 20
    readonly_fields = ('created', 'updated', 'job', 'request', 'response', 'response_status')
    resource_class = import_export.JobLogResource
    search_fields = ('=id', '=job__id', 'url', 'request', 'response', 'response_status')

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
class StandardPointAdmin(ImportExportMixin, admin.ModelAdmin):
    """Геозоны"""
    fields = models.StandardPoint().collect_fields()
    list_display = (
        'id', 'title', 'wialon_id', 'job_template', 'total_time_standard', 'parking_time_standard'
    )
    list_display_links = ('id', 'title')
    list_editable = ('total_time_standard', 'parking_time_standard')
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

    def get_queryset(self, request):
        qs = super(StandardPointAdmin, self).get_queryset(request)
        if request.user.ura_user_id:
            qs = qs.filter(job_template__user=request.user.ura_user)
        return qs


@admin.register(models.StandardJobTemplate)
class StandardJobTemplateAdmin(admin.ModelAdmin):
    """Шаблоны отчетов"""
    date_hierarchy = 'created'
    fields = models.StandardJobTemplate().collect_fields()
    inlines = (StandardPointTabularInline,)
    list_display = ('id', 'title', 'wialon_id', 'space_overstatements_standard')
    list_display_links = ('id', 'title')
    list_editable = ('space_overstatements_standard',)
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

    def get_queryset(self, request):
        qs = super(StandardJobTemplateAdmin, self).get_queryset(request)
        if request.user.ura_user_id:
            qs = qs.filter(user=request.user.ura_user)
        return qs
