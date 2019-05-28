from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import ugettext_lazy as _

from snippets.admin import activate_action, deactivate_action
from users.forms import UserAdminForm, UserCreationForm
from users import models


class UserTotalReportUserInline(admin.TabularInline):
    """Компании, по которым пользователь может получить сводные отчеты"""

    extra = 0
    fields = models.UserTotalReportUser().collect_fields()
    fk_name = 'executor_user'
    model = models.UserTotalReportUser
    raw_id_fields = ('report_user',)
    readonly_fields = ('created', 'updated')
    suit_classes = 'suit-tab suit-tab-total_report'


@admin.register(models.User)
class UserAdmin(UserAdmin):
    """Пользователи"""
    actions = (activate_action, deactivate_action)
    add_form = UserCreationForm
    fieldsets = (
        (None, {
            'classes': ('suit-tab', 'suit-tab-general'),
            'fields': (
                'username', 'email', 'company_name', 'first_name', 'last_name', 'password',
                'is_active', 'created', 'updated'
            )
        }),
        (_('Права доступа'), {
            'classes': ('suit-tab', 'suit-tab-permission'),
            'fields': ('is_staff', 'is_superuser', 'user_permissions')
        }),
        (_('Wialon'), {
            'classes': ('suit-tab', 'suit-tab-wialon'),
            'fields': (
                'wialon_token', 'wialon_username', 'wialon_password', 'timezone',
                'wialon_group_object_name',
                'wialon_resource_name',
                'wialon_discharge_individual_report_template_name',
                'wialon_driving_style_report_template_name',
                'wialon_driving_style_individual_report_template_name',
                'wialon_geozones_report_template_name',
                'wialon_last_data_report_template_name',
                'wialon_sensors_report_template_name',
                'wialon_taxiing_report_template_name',
                'wialon_mobile_vehicle_types'
            )
        }),
        (_('УРА'), {
            'classes': ('suit-tab', 'suit-tab-ura'),
            'fields': ('organization_name', 'supervisor', 'ura_user')
        })
    )
    filter_horizontal = ('user_permissions',)
    form = UserAdminForm
    inlines = (UserTotalReportUserInline,)
    list_display = (
        'username', 'organization_name', 'wialon_username', 'supervisor', 'is_active', 'is_staff'
    )
    list_editable = ('is_active',)
    list_filter = ('is_active', 'is_staff', 'is_superuser', 'groups')
    list_select_related = True
    readonly_fields = ('last_login', 'date_joined', 'wialon_token', 'created', 'updated')
    save_as = True
    search_fields = (
        '=id', 'username', 'email', 'wialon_token', 'organization_name', 'wialon_username'
    )
    suit_form_tabs = (
        ('general', _('Общее')),
        ('permission', _('Права')),
        ('wialon', _('Wialon')),
        ('ura', _('УРА')),
        ('total_report', _('Сводные отчеты'))
    )

    def get_actions(self, request):
        actions = super(UserAdmin, self).get_actions(request)
        if 'delete_selected' in actions and not request.user.is_superuser:
            del actions['delete_selected']
        return actions
