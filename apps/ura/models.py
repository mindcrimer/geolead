# -*- coding: utf-8 -*-
from django.db import models
from django.utils.translation import ugettext_lazy as _

from snippets.models import LastModMixin, BasicModel
from ura.enums import JobLogResolution


class Job(BasicModel, LastModMixin):
    """Путевые листы"""
    name = models.CharField(_('Название'), max_length=255)

    unit_id = models.CharField(_('ID объекта (ТС)'), max_length=100)
    unit_title = models.CharField(
        _('Название объекта (ТС)'), max_length=255, blank=True, null=True
    )

    route_id = models.CharField(_('ID маршрута'), max_length=100)
    route_title = models.CharField(_('Название маршрута'), max_length=255, blank=True, null=True)

    driver_id = models.CharField(_('ID водителя'), max_length=100, blank=True, null=True)
    driver_fio = models.CharField(_('ФИО водителя'), max_length=255, blank=True, null=True)

    date_begin = models.DateTimeField(_('Время начала ПЛ'))
    date_end = models.DateTimeField(_('Время окончания ПЛ'))

    leave_time = models.DateTimeField(_('Время выезда'), blank=True, null=True)
    return_time = models.DateTimeField(_('Время заезда'), blank=True, null=True)

    user = models.ForeignKey(
        'users.User', verbose_name=_('Организация'), blank=True, null=True, related_name='jobs',
        on_delete=models.SET_NULL
    )

    class Meta:
        verbose_name = _('Путевой лист')
        verbose_name_plural = _('Путевые листы')

    def __str__(self):
        return str(self.pk)


class JobLog(BasicModel, LastModMixin):
    """Журнал изменения и запроса данных по путевым листам"""
    job = models.ForeignKey(
        'Job', verbose_name=_('Путевой лист'), related_name='log', blank=True, null=True,
        on_delete=models.SET_NULL
    )
    url = models.CharField(_('URL'), max_length=255, blank=True, null=True, db_index=True)

    request = models.TextField(_('Запрос'), blank=True, null=True)
    user = models.ForeignKey(
        'users.User', verbose_name=_('Пользователь'), blank=True, null=True, related_name='logs',
        on_delete=models.SET_NULL
    )
    response = models.TextField(_('Ответ'), blank=True, null=True)
    response_status = models.PositiveSmallIntegerField(_('Статус ответа'), blank=True, null=True)
    resolution = models.SmallIntegerField(
        _('Резолюция ошибки'), choices=JobLogResolution.get_choices(),
        default=JobLogResolution.default, null=True
    )

    class Meta:
        verbose_name = _('Запись лога путевого листа')
        verbose_name_plural = _('Лог путевого листа')

    def __str__(self):
        return '%s (%s)' % (self.pk, self.response_status)


class JobPoint(BasicModel, LastModMixin):
    """Точки (геозоны путевого листа по мере прохождения"""
    job = models.ForeignKey(
        'Job', verbose_name=_('Путевой лист'), related_name='points', on_delete=models.CASCADE
    )

    title = models.CharField(_('Заголовок'), max_length=255, blank=True, null=True)
    point_type = models.PositiveIntegerField(_('Тип геозоны'), blank=True, null=True)

    enter_date_time = models.DateTimeField(_('Время входа'), blank=True, null=True)
    leave_date_time = models.DateTimeField(_('Время выхода'), blank=True, null=True)

    total_time = models.FloatField(_('Время в геозоне, сек'), blank=True, null=True)
    move_time = models.FloatField(_('Время движения в геозоне, сек'), blank=True, null=True)
    parking_time = models.FloatField(_('Время стоянки в геозоне, сек'), blank=True, null=True)
    motohours_time = models.FloatField(
        _('Время работающего двигателя, сек'), blank=True, null=True
    )
    gpm_time = models.FloatField(_('Время работы ГПМ, сек'), blank=True, null=True)

    lat = models.FloatField(_('Широта входа в геозону'), null=True, blank=True)
    lng = models.FloatField(_('Долгота входа в геозону'), null=True, blank=True)

    class Meta:
        verbose_name = _('Геозона путевого листа')
        verbose_name_plural = _('Геозоны путевого листа')

    def __str__(self):
        return 'ПЛ ID=%s: %s' % (self.job_id, self.title)


class JobPointStop(BasicModel, LastModMixin):
    """Остановки по маршруту ПЛ"""
    job_point = models.ForeignKey(
        'JobPoint', verbose_name=_('Геозона путевого листа'), related_name='stops',
        on_delete=models.CASCADE
    )
    start_date_time = models.DateTimeField(_('Время начала'), blank=True, null=True)
    finish_date_time = models.DateTimeField(_('Время конца'), blank=True, null=True)
    place = models.TextField(_('Местоположение'), blank=True)
    lat = models.FloatField(_('Широта точки остановки'), null=True, blank=True)
    lng = models.FloatField(_('Долгота точки остановки'), null=True, blank=True)

    class Meta:
        verbose_name = _('Остановка по маршруту ПЛ')
        verbose_name_plural = _('Остановки по маршруту ПЛ')

    def __str__(self):
        return '%s: %s' % (self.job_point, self.place)


class StandardJobTemplate(BasicModel, LastModMixin):
    """Маршруты (шаблоны заданий) Wialon"""
    user = models.ForeignKey(
        'users.User', blank=True, null=True, verbose_name=_('Пользователь'),
        related_name='standard_job_templates', on_delete=models.SET_NULL
    )
    wialon_id = models.CharField(_('ID в Wialon'), max_length=64, unique=True)
    title = models.CharField(_('Заголовок'), max_length=255)
    space_overstatements_standard = models.FloatField(
        _('Норматив перенахождения вне плановых геозон, мин.'), null=True, blank=True
    )

    class Meta:
        verbose_name = _('Маршрут Wialon')
        verbose_name_plural = _('Маршруты Wialon')

    def __str__(self):
        return self.title


class StandardPoint(BasicModel, LastModMixin):
    """Плановые геозоны маршрута (шаблона задания)"""
    job_template = models.ForeignKey(
        'StandardJobTemplate', related_name='points', verbose_name=_('Шаблон отчетов (маршрут)'),
        on_delete=models.CASCADE
    )
    wialon_id = models.CharField(_('ID в Wialon'), max_length=64)
    title = models.CharField(_('Заголовок'), max_length=255)
    total_time_standard = models.FloatField(
        _('Норматив времени нахождения, мин.'), null=True, blank=True
    )
    parking_time_standard = models.FloatField(
        _('Норматив времени стоянок, мин.'), null=True, blank=True
    )

    class Meta:
        unique_together = ('job_template', 'wialon_id')
        verbose_name = _('Геозона Wialon')
        verbose_name_plural = _('Геозоны Wialon')

    def __str__(self):
        return self.title
