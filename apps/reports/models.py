# -*- coding: utf-8 -*-
from django.db import models
from django.utils.translation import ugettext_lazy as _

from snippets.models import BasicModel, LastModMixin


class ReportLog(LastModMixin, BasicModel):
    """Лог отчетов"""
    user = models.ForeignKey(
        'users.User', related_name='report_logs', verbose_name=_('Пользователь')
    )

    class Meta:
        verbose_name = _('Запись лога отчетов')
        verbose_name_plural = _('Логи отчетов')
