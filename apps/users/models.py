from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import ugettext_lazy as _

from timezone_field import TimeZoneField

from snippets.models import LastModMixin, BasicModel, BaseModel
from users.managers import UserManager


class User(AbstractUser, LastModMixin, BasicModel):
    """Модель профилей"""
    REQUIRED_FIELDS = ['email']

    username = models.CharField(
        _('username'),
        max_length=150,
        unique=True,
        help_text=_('Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.'),
        error_messages={
            'unique': _("A user with that username already exists."),
        },
    )

    first_name = models.CharField(
        _('Имя ответственного лица'), max_length=150, blank=True, null=True
    )
    last_name = models.CharField(
        _('Фамилия ответственного лица'), max_length=150, blank=True, null=True
    )
    email = models.CharField(
        _('email address'), blank=True, max_length=255, help_text='Можно указать через запятую'
    )
    company_name = models.CharField('Название компании', blank=True, null=True, max_length=255)

    wialon_token = models.CharField(_('Токен в Wialon'), blank=True, null=True, max_length=255)
    wialon_username = models.CharField(_('Логин в Wialon'), max_length=255, blank=True, null=True)
    wialon_password = models.CharField(_('Пароль в Wialon'), max_length=100, blank=True, null=True)

    wialon_group_object_name = models.CharField(
        _('Наименование группового объекта'), max_length=255, blank=True, null=True
    )
    wialon_resource_name = models.CharField(
        _('Наименование ресурса'), max_length=255, blank=True, null=True
    )

    wialon_discharge_individual_report_template_name = models.CharField(
        _('Наименование отчета "Перерасход топлива индивидуальный"'), max_length=255, blank=True,
        null=True
    )
    wialon_driving_style_report_template_name = models.CharField(
        _('Наименование отчета "Качество вождения (БДД)"'), max_length=255, blank=True, null=True
    )
    wialon_driving_style_individual_report_template_name = models.CharField(
        _('Наименование отчета "Качество вождения индивидуальный (БДД)"'), max_length=255,
        blank=True, null=True
    )
    wialon_geozones_report_template_name = models.CharField(
        _('Наименование отчета "Геозоны"'), max_length=255, blank=True, null=True
    )
    wialon_last_data_report_template_name = models.CharField(
        _('Наименование отчета "Последние данные"'), max_length=255, blank=True, null=True
    )
    wialon_sensors_report_template_name = models.CharField(
        _('Наименование отчета "Неисправности"'), max_length=255, blank=True, null=True
    )
    wialon_taxiing_report_template_name = models.CharField(
        _('Наименование отчета "Таксировка"'), max_length=255, blank=True, null=True
    )

    wialon_mobile_vehicle_types = models.CharField(
        _('Список мобильных типов ТС, по которым необходимы отчеты ПДД'),
        max_length=255, blank=True, null=True,
        help_text=_(
            'Через ЗАПЯТУЮ. Пробелы между типами и регистр значения не имеют. '
            'Если не указан список типов, допускаем наличие любых ТС в отчетах по ПДД. '
            'Объекты, у которых в характеристиках не указан тип ТС, также включаются в отчеты.'
        )
    )

    timezone = TimeZoneField(default='UTC', verbose_name=_('Часовой пояс'))
    organization_name = models.CharField(
        _('Название организации в УРА'), blank=True, null=False, max_length=255
    )
    ura_user = models.ForeignKey(
        'self', verbose_name=_('Просмотр данных УРА от лица пользователя УРА'),
        blank=True, null=True,
        related_name='ura_subordinates',
        help_text=_(
            'В случае отсутствия будет показывать все данные УРА (ПЛ, нормативы). При задании '
            'позволяет операторам получать отчеты от лица головной учетной записи'
        ),
        on_delete=models.SET_NULL
    )
    supervisor = models.ForeignKey(
        'self', blank=True, null=True, verbose_name=_('Супервайзер'),
        help_text=_(
            'Указание супервайзера позволит УРА работать сразу с несколькими учетными записями '
            'под одним логин/паролем'
        ),
        on_delete=models.SET_NULL
    )

    class Meta:
        ordering = ('username',)
        verbose_name = _('Профиль пользователя')
        verbose_name_plural = _('Профили пользователей')

    objects = UserManager()

    def __str__(self):
        return self.username

    def get_organization_name(self):
        return self.organization_name if self.organization_name else self.username

    def get_full_name(self):
        fn = ' '.join(filter(lambda x: x, (self.first_name, self.last_name)))
        return fn if fn else self.username

    @property
    def full_name(self):
        return self.get_full_name()


class UserTotalReportUser(BaseModel):
    """Компании сводного отчета на выбор получателя отчета"""

    executor_user = models.ForeignKey(
        'users.User', verbose_name='Получатель отчета', related_name='total_report_companies',
        on_delete=models.CASCADE
    )
    report_user = models.ForeignKey(
        'users.User', related_name='total_report_executors',
        verbose_name='Аккаунт, по которому составляется отчет', on_delete=models.CASCADE
    )

    class Meta:
        ordering = ('ordering',)
        verbose_name = 'Подчиненная компания для сводных отчетов'
        verbose_name_plural = 'Подчиненные компании для сводных отчетов'
