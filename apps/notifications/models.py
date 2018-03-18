# -*- coding: utf-8 -*-
from django.db import models
from django.utils.translation import ugettext_lazy as _

from snippets.models import BasicModel, LastModMixin


class Notification(LastModMixin, BasicModel):
    """Шаблоны уведомлений"""
    job = models.ForeignKey(
        'ura.Job', verbose_name=_('Путевой лист'), related_name='notifications'
    )

    class Meta:
        verbose_name = _('Шаблон уведомлений')
        verbose_name_plural = _('Шаблоны уведомлений')


class Event(LastModMixin, BasicModel):
    """События"""
    class Meta:
        verbose_name = _('Событие')
        verbose_name_plural = _('События')
