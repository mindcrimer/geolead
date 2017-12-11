# -*- coding: utf-8 -*-
from django.db import models
from django.utils.translation import ugettext_lazy as _

from snippets.models import LastModMixin, BasicModel
from ura.enums import JobExecutionStatusEnum


class UraJob(BasicModel, LastModMixin):
    """Путевые листы"""
    name = models.CharField(_('Название'), max_length=255)
    unit_id = models.CharField(_('idUnit'), max_length=255)
    route_id = models.CharField(_('idRoute'), max_length=255)
    driver_id = models.CharField(_('idDriver'), max_length=255, blank=True, null=True)
    driver_fio = models.CharField(_('ФИО водителя'), max_length=255, blank=True, null=True)

    date_begin = models.DateTimeField(_('Дата/время начала'))
    date_end = models.DateTimeField(_('Дата/время конца'))
    return_time = models.DateTimeField(_('Дата/время return'), blank=True, null=True)
    leave_time = models.DateTimeField(_('Дата/время leave'), blank=True, null=True)

    execution_status = models.CharField(
        _('Статус прохождения (актуальности)'), max_length=50,
        choices=JobExecutionStatusEnum.get_choices(),
        default=JobExecutionStatusEnum.default
    )

    class Meta:
        verbose_name = _('Путевой лист')
        verbose_name_plural = _('Путевые листы')


class UraJobPoint(BasicModel, LastModMixin):
    """Точки (геозоны путевого листа по мере прохождения"""
    job = models.ForeignKey('UraJob', verbose_name=_('Путевой лист'), related_name='points')

    title = models.CharField(_('Заголовок'), max_length=255, blank=True, null=True)
    point_type = models.PositiveIntegerField(_('Тип геозоны'), blank=True, null=True)

    enter_date_time = models.DateTimeField(_('Время входа'), blank=True, null=True)
    leave_date_time = models.DateTimeField(_('Время выхода'), blank=True, null=True)

    total_time = models.FloatField(_('Время в геозоне, сек'), blank=True, null=True)
    parking_time = models.FloatField(_('Время стоянки в геозоне, сек'), blank=True, null=True)

    class Meta:
        verbose_name = _('Геозона путевого листа')
        verbose_name_plural = _('Геозоны путевого листа')


class StandardJobTemplate(BasicModel, LastModMixin):
    wialon_id = models.IntegerField(_('ID в WIalon'))
    title = models.CharField(_('Заголовок'), max_length=255)
    space_overstatements_standard = models.PositiveIntegerField(
        _('Норматив перепростоя вне плановых геозон, мин.'), null=True, blank=True
    )

    class Meta:
        verbose_name = _('Маршрут Wialon')
        verbose_name_plural = _('Маршруты Wialon')


class StandardPoint(BasicModel, LastModMixin):
    """Плановые геозоны маршрута (шаблона задания)"""
    template_id = models.IntegerField(_('ID шаблона отчета (маршрута)'))
    wialon_id = models.IntegerField(_('ID в WIalon'))
    title = models.CharField(_('Заголовок'), max_length=255)
    total_time_standard = models.PositiveIntegerField(
        _('Норматив времени нахождения, мин.'), null=True, blank=True
    )
    parking_time_standard = models.PositiveIntegerField(
        _('Норматив времени остановок, мин.'), null=True, blank=True
    )

    class Meta:
        verbose_name = _('Геозона Wialon')
        verbose_name_plural = _('Геозоны Wialon')
