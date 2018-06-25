from django.db import models
from django.utils.translation import ugettext_lazy as _

from snippets.models import BasicModel, LastModMixin
from snippets.utils.passwords import generate_uuid4


class Report(LastModMixin, BasicModel):
    """Отчеты"""
    uid = models.CharField(
        _('Идентификатор'), unique=True, max_length=36, default=generate_uuid4
    )
    user = models.ForeignKey(
        'users.User', related_name='report_logs', verbose_name=_('Пользователь'),
        on_delete=models.CASCADE
    )

    class Meta:
        verbose_name = _('Отчет')
        verbose_name_plural = _('Отчеты')


class ReportLog(LastModMixin, BasicModel):
    """Лог отчетов"""
    report = models.ForeignKey(
        'reports.Report', verbose_name=_('Отчет'), related_name='logs', on_delete=models.CASCADE
    )
    log_message = models.TextField(_('Сообщение'), blank=True)

    class Meta:
        verbose_name = _('Запись лога отчетов')
        verbose_name_plural = _('Логи отчетов')


class WialonReportLog(LastModMixin, BasicModel):
    """Лог отчетов"""
    user = models.ForeignKey(
        'users.User', related_name='wialon_report_logs', verbose_name=_('Пользователь'),
        on_delete=models.CASCADE
    )

    class Meta:
        verbose_name = _('Выполнение отчета')
        verbose_name_plural = _('Счетчик выполнения отчетов в Wialon')
