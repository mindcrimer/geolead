# -*- coding: utf-8 -*-
from django.contrib import admin

from ura import models


@admin.register(models.UraJob)
class UraJobAdmin(admin.ModelAdmin):
    """Предложение новой категории"""
    date_hierarchy = 'created'
    fields = models.UraJob().collect_fields() + ['created', 'updated']
    list_display = ('id', 'name', 'driver_fio', 'date_begin', 'date_end')
    list_display_links = ('id', 'name')
    ordering = ('-created',)
    readonly_fields = ('created', 'updated')
    search_fields = ('=id', 'name', 'unit_id', 'route_id', 'driver_id', 'driver_fio')

    def has_add_permission(self, request):
        return False
