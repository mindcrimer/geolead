from django.contrib import admin

from reports import models
from snippets.admin import BaseModelAdmin


class AbstractReportDelivery(BaseModelAdmin):
    list_display = ('id', 'work_title', 'status', 'created')
    list_display_links = ('id', 'work_title')
    list_editable = ('status',)
    filter_horizontal = ('users',)
    readonly_fields = ('created', 'updated')
    search_fields = (
        '=id', 'work_title', 'users__email', 'users__username', 'users__first_name',
        'users__last_name'
    )


@admin.register(models.DrivingStyleReportDelivery)
class DrivingStyleReportDeliveryAdmin(AbstractReportDelivery):
    """
    Настройки рассылки отчета по БДД
    """
    fields = models.DrivingStyleReportDelivery().collect_fields() + ['users']


@admin.register(models.DrivingStyleTotalReportDelivery)
class DrivingStyleTotalReportDeliveryAdmin(AbstractReportDelivery):
    """
    Настройки рассылки отчета по БДД (Сводный)
    """
    fields = models.DrivingStyleTotalReportDelivery().collect_fields() + ['users']


@admin.register(models.FaultsReportDelivery)
class FaultsReportDeliveryAdmin(AbstractReportDelivery):
    """
    Настройки рассылки отчета о состоянии оборудования
    """
    list_display = list(AbstractReportDelivery.list_display[:])
    list_display.insert(2, 'job_extra_offset')
    fields = models.FaultsReportDelivery().collect_fields() + ['users']


def re_send_email(modeladmin, request, queryset):
    """
    Повторить отправку писем
    :param modeladmin:
    :param request:
    :param queryset:
    :return:
    """
    for log in queryset.filter(success=False):
        log.send()


re_send_email.short_description = 'Повторить отправку'


@admin.register(models.ReportEmailDeliveryLog)
class ReportEmailDeliveryLogAdmin(admin.ModelAdmin):
    """
    Лог рассылки отчета
    """
    actions = admin.ModelAdmin.actions + [re_send_email]
    date_hierarchy = 'created'
    fields = models.ReportEmailDeliveryLog().collect_fields()
    list_display = ('user', 'email', 'report_type', 'success', 'created')
    list_filter = ('report_type', 'success')
    list_select_related = True
    readonly_fields = models.ReportEmailDeliveryLog().collect_fields()
    readonly_fields.remove('success')
    search_fields = (
        '=id', 'user__email', 'user__username', 'user__first_name', 'user__last_name', 'email'
    )
