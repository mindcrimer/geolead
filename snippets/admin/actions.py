# -*- coding: utf-8 -*-
from django.utils.translation import ugettext_lazy as _


def deactivate_action(modeladmin, request, queryset):
    queryset.update(is_active=False)


deactivate_action.short_description = _('Деактивировать')


def activate_action(modeladmin, request, queryset):
    queryset.update(is_active=True)


activate_action.short_description = _('Активировать')
