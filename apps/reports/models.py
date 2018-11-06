from django.db import models
from django.utils.translation import ugettext_lazy as _
from reports.enums import EmailDeliveryReportTypeEnum

from snippets.models import BasicModel, LastModMixin, BaseModel
from snippets.utils.passwords import generate_uuid4


class Report(LastModMixin, BasicModel):
    """
    Отчеты
    """
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
    """
    Лог отчетов
    """
    report = models.ForeignKey(
        'reports.Report', verbose_name=_('Отчет'), related_name='logs', on_delete=models.CASCADE
    )
    log_message = models.TextField(_('Сообщение'), blank=True)

    class Meta:
        verbose_name = _('Запись лога отчетов')
        verbose_name_plural = _('Логи отчетов')


class WialonReportLog(LastModMixin, BasicModel):
    """
    Лог отчетов
    """
    user = models.ForeignKey(
        'users.User', related_name='wialon_report_logs', verbose_name=_('Пользователь'),
        on_delete=models.CASCADE
    )

    class Meta:
        verbose_name = _('Выполнение отчета')
        verbose_name_plural = _('Счетчик выполнения отчетов в Wialon')


class AbstractReportDelivery(BaseModel):
    """
    Настройка рассыллок отчетов
    """
    work_title = models.CharField('Рабочее название настроек', max_length=255)

    class Meta:
        abstract = True
        verbose_name = _('Настройка рассылки отчета')
        verbose_name_plural = _('Настройка рассылок отчета')


class FaultsReportDelivery(AbstractReportDelivery):
    """
    Настройка рассыллок отчетов
    """
    job_extra_offset = models.PositiveSmallIntegerField(
        _('Дополнительное время до и после ПЛ, ч'), default=2
    )

    users = models.ManyToManyField(
        'users.User', verbose_name='Пользователи', blank=False,
        related_name='faults_report_delivery_settings'
    )

    class Meta:
        verbose_name = _('Настройка рассылки отчета "Состояние оборудования"')
        verbose_name_plural = _('Настройка рассылок отчета "Состояние оборудования"')


class DrivingStyleReportDelivery(AbstractReportDelivery):
    """
    Настройка рассыллок отчетов
    """
    users = models.ManyToManyField(
        'users.User', verbose_name='Пользователи', blank=False,
        related_name='driving_style_report_delivery_settings'
    )

    class Meta:
        verbose_name = _('Настройка рассылки отчета "Качество вождения"')
        verbose_name_plural = _('Настройка рассылок отчета "Качество вождения"')


class ReportEmailDeliveryLog(BasicModel, LastModMixin):
    """
    Лог доставки отчетов
    """
    user = models.ForeignKey('users.User', verbose_name='Пользователь', related_name='email_logs')
    email = models.EmailField('Email пользователя', max_length=254)
    report_type = models.CharField(
        'Тип отчета', choices=EmailDeliveryReportTypeEnum.get_choices(), max_length=50
    )
    report = models.FileField('Отчет', max_length=255, upload_to='reports/%Y/%m/%d')

    class Meta:
        ordering = ('-created',)
        verbose_name = _('Настройка рассылки отчета "Качество вождения"')
        verbose_name_plural = _('Настройка рассылок отчета "Качество вождения"')
