# -*- coding: utf-8 -*-
from django.contrib import admin

from ura import models


class UraJobLogTabularInline(admin.TabularInline):
    extra = 0
    fields = models.UraJobLog().collect_fields()
    model = models.UraJobLog
    ordering = ('-created',)

    def has_add_permission(self, request):
        return False


@admin.register(models.UraJob)
class UraJobAdmin(admin.ModelAdmin):
    """Заявки"""
    date_hierarchy = 'created'
    fields = models.UraJob().collect_fields()
    inlines = (UraJobLogTabularInline,)
    list_display = ('id', 'name', 'driver_fio', 'date_begin', 'date_end')
    list_display_links = ('id', 'name')
    ordering = ('-created',)
    readonly_fields = ('created', 'updated', 'execution_status')
    search_fields = ('=id', 'name', 'unit_id', 'route_id', 'driver_id', 'driver_fio')

    def has_add_permission(self, request):
        return False
