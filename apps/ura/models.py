# -*- coding: utf-8 -*-
from django.db import models
from django.utils.translation import ugettext_lazy as _

from snippets.models import LastModMixin, BasicModel


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

    class Meta:
        verbose_name = _('Путевой лист')
        verbose_name_plural = _('Путевые листы')


class UraJobLog(BasicModel, LastModMixin):
    """Журнал изменения и запроса данных по путевым листам"""
    job = models.ForeignKey(
        'UraJob', verbose_name=_('Путевой лист'), related_name='log', blank=True, null=True
    )
    request = models.TextField(_('Запрос'), blank=True, null=True)
    user = models.ForeignKey(
        'users.User', verbose_name=_('Пользователь'), blank=True, null=True, related_name='logs'
    )
    response = models.TextField(_('Ответ'), blank=True, null=True)
    response_status = models.PositiveSmallIntegerField(_('Статус ответа'), blank=True, null=True)

    class Meta:
        verbose_name = _('Запись лога путевого листа')
        verbose_name_plural = _('Лог путевого листа')

    def __str__(self):
        return '%s (%s)' % (self.pk, self.response_status)


class UraJobPoint(BasicModel, LastModMixin):
    """Точки (геозоны путевого листа по мере прохождения"""
    job = models.ForeignKey('UraJob', verbose_name=_('Путевой лист'), related_name='points')

    title = models.CharField(_('Заголовок'), max_length=255, blank=True, null=True)
    point_type = models.PositiveIntegerField(_('Тип геозоны'), blank=True, null=True)

    enter_date_time = models.DateTimeField(_('Время входа'), blank=True, null=True)
    leave_date_time = models.DateTimeField(_('Время выхода'), blank=True, null=True)

    total_time = models.FloatField(_('Время в геозоне, сек'), blank=True, null=True)
    parking_time = models.FloatField(_('Время стоянки в геозоне, сек'), blank=True, null=True)

    lat = models.FloatField(_('Широта входа в геозону'), null=True, blank=True)
    lng = models.FloatField(_('Долгота входа в геозону'), null=True, blank=True)

    class Meta:
        verbose_name = _('Геозона путевого листа')
        verbose_name_plural = _('Геозоны путевого листа')

    def __str__(self):
        return str(self.pk)


class StandardJobTemplate(BasicModel, LastModMixin):
    user = models.ForeignKey(
        'users.User', blank=True, null=True, verbose_name=_('Пользователь'),
        related_name='standard_job_templates'
    )
    wialon_id = models.CharField(_('ID в WIalon'), max_length=64, unique=True)
    title = models.CharField(_('Заголовок'), max_length=255)
    space_overstatements_standard = models.PositiveIntegerField(
        _('Норматив перепростоя вне плановых геозон, мин.'), null=True, blank=True
    )

    class Meta:
        verbose_name = _('Маршрут Wialon')
        verbose_name_plural = _('Маршруты Wialon')

    def __str__(self):
        return self.title


class StandardPoint(BasicModel, LastModMixin):
    """Плановые геозоны маршрута (шаблона задания)"""
    job_template = models.ForeignKey(
        'StandardJobTemplate', related_name='points', verbose_name=_('Шаблон отчетов (маршрут)')
    )
    wialon_id = models.CharField(_('ID в WIalon'), max_length=64)
    title = models.CharField(_('Заголовок'), max_length=255)
    total_time_standard = models.PositiveIntegerField(
        _('Норматив времени нахождения, мин.'), null=True, blank=True
    )
    parking_time_standard = models.PositiveIntegerField(
        _('Норматив времени стоянок, мин.'), null=True, blank=True
    )

    class Meta:
        unique_together = ('job_template', 'wialon_id')
        verbose_name = _('Геозона Wialon')
        verbose_name_plural = _('Геозоны Wialon')

    def __str__(self):
        return self.title
