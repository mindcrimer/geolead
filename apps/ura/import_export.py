# -*- coding: utf-8 -*-
from import_export import resources, fields

from ura import models


class StandardPointResource(resources.ModelResource):
    job_template_user = fields.Field(
        attribute='job_template_user', column_name='job_template_user'
    )
    space_overstatements_standard = fields.Field(
        attribute='space_overstatements_standard',
        column_name='Норматив перепростоя вне плановых геозон, мин.'
    )
    total_time_standard = fields.Field(
        attribute='total_time_standard',
        column_name='Норматив времени нахождения, мин.'
    )
    parking_time_standard = fields.Field(
        attribute='parking_time_standard',
        column_name='Норматив времени стоянок, мин.'
    )

    class Meta:
        fields = ('id', 'job_template', 'wialon_id', 'title')
        export_order = fields + (
            'job_template_user', 'space_overstatements_standard', 'total_time_standard',
            'parking_time_standard'
        )
        model = models.StandardPoint
        skip_unchanged = True

    @staticmethod
    def dehydrate_job_template(obj):
        return str(obj.job_template)

    @staticmethod
    def dehydrate_job_template_user(obj):
        return str(obj.job_template.user)

    @staticmethod
    def dehydrate_space_overstatements_standard(obj):
        return obj.job_template.space_overstatements_standard\
            if obj.job_template.space_overstatements_standard else ''


class UraJobLogResource(resources.ModelResource):

    class Meta:
        fields = ('id', 'job', 'url', 'request', 'user', 'response', 'response_status', 'created')
        export_order = fields
        model = models.UraJobLog
        skip_unchanged = True

    @staticmethod
    def dehydrate_user(obj):
        return obj.user.username if obj.user_id else ''
