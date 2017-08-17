# -*- coding: utf-8 -*-
from django.contrib.admin import ModelAdmin

from snippets.utils.array import move_list_element_to_end


class SuperUserDeletableAdminMixin(object):
    @staticmethod
    def has_delete_permission(request, obj=None):
        return request.user.is_superuser


class BaseModelAdmin(ModelAdmin):
    """Базовый класс для админ.части модели BaseModel"""
    list_display = ('id', 'status', 'ordering', 'created')
    list_editable = ('status', 'ordering')
    list_filter = ('status',)
    ordering = ('ordering',)
    readonly_fields = ('created', 'updated')

    def get_fieldsets(self, request, obj=None):
        fieldsets = super(BaseModelAdmin, self).get_fieldsets(request, obj=obj)

        for field in ('created', 'updated'):
            if field not in fieldsets[0][1]['fields']:
                fieldsets[0][1]['fields'].append(field)

        return fieldsets


class ModelTranlsationFieldsetsMixin(object):
    def get_fieldsets(self, request, obj=None):
        fieldsets = super(ModelTranlsationFieldsetsMixin, self).get_fieldsets(request, obj=obj)

        if not hasattr(self, 'tabs_mapping'):
            return fieldsets

        fieldsets_to_remove = []
        for i, fieldset in enumerate(fieldsets):
            title = fieldset[0]
            if title in self.tabs_mapping:
                if 'classes' not in fieldset[1]:
                    fieldset[1]['classes'] = ()
                fieldset[1]['classes'] += (
                    ('suit-tab', 'suit-tab-%s' % self.tabs_mapping[title])
                )
            elif i != 0:
                for field in reversed(fieldset[1]['fields']):
                    fieldsets[0][1]['fields'].insert(0, field)
                fieldsets_to_remove.append(fieldset)

        if fieldsets_to_remove:
            for fieldset in fieldsets_to_remove:
                fieldsets.remove(fieldset)

        for field in ('status', 'ordering'):
            if field in fieldsets[0][1]['fields']:
                move_list_element_to_end(fieldsets[0][1]['fields'], field)

        return fieldsets
