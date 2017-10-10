# -*- coding: utf-8 -*-
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin, GroupAdmin as DjangoGroupAdmin
from django.contrib.auth.models import Group
from django.utils.translation import ugettext_lazy as _

from snippets.admin import activate_action, deactivate_action
from users.forms import UserAdminForm, UserCreationForm
from users import models


admin.site.unregister(Group)


@admin.register(Group)
class GroupAdmin(DjangoGroupAdmin):
    pass


@admin.register(models.User)
class UserAdmin(UserAdmin):
    """Пользователи"""
    actions = (activate_action, deactivate_action)
    add_form = UserCreationForm
    fieldsets = (
        (None, {
            'classes': ('suit-tab', 'suit-tab-general'),
            'fields': (
                'is_active', 'username', 'password', 'user_permissions', 'created', 'updated'
            )
        }),
        (_('Персональная информация'), {
            'classes': ('suit-tab', 'suit-tab-general'),
            'fields': ('last_name', 'first_name', 'middle_name', 'email')
        }),
        (_('Важные даты'), {
            'classes': ('suit-tab', 'suit-tab-general'),
            'fields': ('last_login', 'date_joined')
        }),
        (_('Права доступа'), {
            'classes': ('suit-tab', 'suit-tab-permission'),
            'fields': ('is_staff', 'is_superuser')
        }),
        (_('Wialon'), {
            'classes': ('suit-tab', 'suit-tab-wialon'),
            'fields': (
                'wialon_token', 'organization_name', 'supervisor', 'wialon_tz',
                'wialon_report_object_id', 'wialon_report_resource_id',
                'wialon_discharge_report_template_id', 'wialon_driving_style_report_template_id',
                'wialon_geozones_report_template_id'
            )
        }),
        (_('УРА'), {
            'classes': ('suit-tab', 'suit-tab-ura'),
            'fields': ('ura_tz',)
        })
    )
    form = UserAdminForm
    list_display = (
        'username', 'get_full_name', 'organization_name', 'is_active', 'is_staff', 'is_superuser'
    )
    list_filter = ('is_active', 'is_staff', 'is_superuser', 'groups')
    readonly_fields = ('last_login', 'date_joined', 'created', 'updated', 'full_name')
    search_fields = ('=id', 'username', 'full_name', 'email', 'wialon_token', 'organization_name')
    suit_form_tabs = (
        ('general', _('Общее')),
        ('permission', _('Права')),
        ('wialon', _('Wialon')),
        ('ura', _('УРА'))
    )

    def get_actions(self, request):
        actions = super(UserAdmin, self).get_actions(request)
        if 'delete_selected' in actions and not request.user.is_superuser:
            del actions['delete_selected']
        return actions
