# -*- coding: utf-8 -*-
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import ugettext_lazy as _

from snippets.models import LastModMixin, BasicModel
from timezone_field import TimeZoneField
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

    wialon_token = models.CharField(_('Токен в Wialon'), blank=True, null=True, max_length=255)
    wialon_username = models.CharField(_('Логин в Wialon'), max_length=255, blank=True, null=True)

    wialon_report_object_id = models.BigIntegerField(
        _('ID группового объекта для отчетов в Wialon'), blank=True, null=True
    )
    wialon_report_resource_id = models.BigIntegerField(
        _('ID ресурса отчетов в Wialon'), blank=True, null=True
    )
    wialon_discharge_report_template_id = models.BigIntegerField(
        _('ID отчета "Перерасход топлива" в Wialon'), blank=True, null=True
    )
    wialon_driving_style_report_template_id = models.BigIntegerField(
        _('ID шаблона отчета "Стиль вождения" в Wialon'), blank=True, null=True
    )
    wialon_geozones_report_template_id = models.BigIntegerField(
        _('ID шаблона отчета "Геозоны" в Wialon'), blank=True, null=True
    )
    wialon_kmu_report_template_id = models.BigIntegerField(
        _('ID шаблона отчета "Работа крановой установки" в Wialon'), blank=True, null=True
    )
    wialon_tz = TimeZoneField(default='UTC', verbose_name=_('Часовой пояс Wialon'))

    ura_tz = TimeZoneField(default='UTC', verbose_name=_('Часовой пояс УРА'))
    organization_name = models.CharField(
        _('Название организации в Wialon'), blank=True, null=False, max_length=255
    )
    supervisor = models.ForeignKey(
        'self', blank=True, null=True, verbose_name=_('Супервайзер'),
        help_text=_(
            'Указание супервайзера позволит УРА работать сразу с несколькими учетными записями '
            'под одним логин/паролем'
        )
    )

    class Meta:
        verbose_name = _('Профиль пользователя')
        verbose_name_plural = _('Профили пользователей')

    objects = UserManager()

    def __str__(self):
        return self.username
