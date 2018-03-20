# -*- coding: utf-8 -*-
from django.contrib.postgres.fields import JSONField

from django.db import models
from django.utils.translation import ugettext_lazy as _

from snippets.models import BasicModel, LastModMixin


class Notification(LastModMixin, BasicModel):
    """Шаблоны уведомлений"""
    job = models.ForeignKey(
        'ura.Job', verbose_name=_('Путевой лист'), related_name='notifications'
    )
    wialon_id = models.IntegerField(_('ID в Wialon'))
    sent_data = JSONField(_('Данные отправленные'), blank=True)
    received_data = JSONField(_('Данные полученные'), blank=True)
    expired_at = models.DateTimeField(_('Срок жизни'), blank=True, null=True)

    class Meta:
        verbose_name = _('Шаблон уведомления')
        verbose_name_plural = _('Шаблоны уведомлений')


class Event(LastModMixin, BasicModel):
    """События"""
    notification = models.ForeignKey(
        'Notification', verbose_name=_('Шаблон уведомления'), related_name='events'
    )

    class Meta:
        verbose_name = _('Событие')
        verbose_name_plural = _('События')
