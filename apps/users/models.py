# -*- coding: utf-8 -*-
import pytz
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import ugettext_lazy as _

from snippets.models import LastModMixin, BasicModel
from timezone_field import TimeZoneField
from users.managers import UserManager


class User(AbstractUser, LastModMixin, BasicModel):
    """Модель профилей"""
    REQUIRED_FIELDS = ['email']

    first_name = models.CharField(
        _('Имя ответственного лица'), max_length=150, blank=True, null=True
    )
    last_name = models.CharField(
        _('Фамилия ответственного лица'), max_length=150, blank=True, null=True
    )
    middle_name = models.CharField(
        _('Отчество ответственного лица'), max_length=150, blank=True, null=True
    )
    full_name = models.TextField(_('ФИО ответственного лица'), max_length=500, blank=True)

    wialon_token = models.CharField(_('Токен в Wialon'), blank=True, null=True, max_length=255)
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

    ura_tz = TimeZoneField(default='UTC', verbose_name=_('Часовой пояс УРА'))
    wialon_tz = TimeZoneField(default='UTC', verbose_name=_('Часовой пояс Wialon'))

    class Meta:
        verbose_name = _('Профиль пользователя')
        verbose_name_plural = _('Профили пользователей')

    objects = UserManager()

    def __str__(self):
        return self.full_name

    def get_full_name(self):
        parts = filter(
            None, (self.last_name, self.first_name, self.middle_name)
        )
        full_name = ' '.join(parts)

        return full_name or self.username
    get_full_name.short_description = 'Полное имя'
    get_full_name.admin_order_field = 'full_name'

    def save(self, *args, **kwargs):
        self.full_name = self.get_full_name()
        return super(User, self).save(*args, **kwargs)
