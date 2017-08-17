# -*- coding: utf-8 -*-
from django.contrib import admin

from snippets.admin import BaseModelAdmin, SuperUserDeletableAdminMixin
from snippets.general import models


@admin.register(models.DbConfig)
class DbConfigAdmin(SuperUserDeletableAdminMixin, BaseModelAdmin):
    """Переменные шаблонов"""
    fields = models.DbConfig().collect_fields()
    list_display = ('key', 'verbose_title', 'status', 'created')
    list_editable = ('status',)
    ordering = ('key',)
    search_fields = ['=id', 'key', 'verbose_title', 'value']


class MenuItemInline(admin.StackedInline):
    """Пункты меню"""
    extra = 0
    fields = models.MenuItem().collect_fields()
    model = models.MenuItem
    raw_id_fields = ('parent_item',)


@admin.register(models.Menu)
class MenuAdmin(SuperUserDeletableAdminMixin, BaseModelAdmin):
    """Меню"""
    fields = models.Menu().collect_fields()
    inlines = (MenuItemInline,)
    list_display = ('slug', 'title', 'status', 'created')
    list_editable = ('status',)
    ordering = BaseModelAdmin.ordering + ('slug',)
    search_fields = ['=id', 'slug', 'title']


@admin.register(models.MenuItem)
class MenuItemAdmin(SuperUserDeletableAdminMixin, BaseModelAdmin):
    """Пункты меню"""
    fields = models.MenuItem().collect_fields()
    list_display = ('id', 'title', 'parent_item', 'menu', 'status', 'ordering', 'created')
    list_display_links = ('id', 'title')
    list_filter = BaseModelAdmin.list_filter + ('menu',)
    ordering = BaseModelAdmin.ordering
    raw_id_fields = ('parent_item',)
    search_fields = ['=id']
