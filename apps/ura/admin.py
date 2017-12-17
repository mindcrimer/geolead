# -*- coding: utf-8 -*-
from django.contrib import admin
from django.contrib.admin import TabularInline

from ura import models


class UraJobLogTabularInline(admin.TabularInline):
    extra = 0
    fields = models.UraJobLog().collect_fields()
    model = models.UraJobLog
    ordering = ('-created',)
    readonly_fields = ('created', 'updated')

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


@admin.register(models.StandardJobTemplate)
class StandardJobTemplateAdmin(admin.ModelAdmin):
    """Шаблоны отчетов"""
    date_hierarchy = 'created'
    fields = models.StandardJobTemplate().collect_fields()
    inlines = (StandardPointTabularInline,)
    list_display = ('id', 'title', 'wialon_id', 'created', 'updated')
    list_display_links = ('id', 'title')
    ordering = ('-created',)
    readonly_fields = ('created', 'updated')
    search_fields = ('=id', '=wialon_id', 'title', 'points__title', 'points__wialon_id')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
