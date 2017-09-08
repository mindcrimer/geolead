# -*- coding: utf-8 -*-
from django.db import models
from django.utils.translation import ugettext_lazy as _

from snippets.models import LastModMixin, BasicModel


class UraJob(BasicModel, LastModMixin):
    """Путевые листы"""
    name = models.CharField(_('Название'), max_length=255, db_index=True, unique=True)
    unit_id = models.PositiveIntegerField(_('idUnit'))
    driver_id = models.CharField(_('idDriver'), max_length=255)
    driver_fio = models.CharField(_('ФИО водителя'), max_length=255)

    date_begin = models.DateTimeField(_('Дата/время начала'))
    date_end = models.DateTimeField(_('Дата/время конца'))
    return_time = models.DateTimeField(_('Дата/время return'))
    leave_time = models.DateTimeField(_('Дата/время leave'))

    class Meta:
        verbose_name = _('Путевой лист')
        verbose_name_plural = _('Путевые листы')
