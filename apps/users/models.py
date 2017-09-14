# -*- coding: utf-8 -*-
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import ugettext_lazy as _

from snippets.models import LastModMixin, BasicModel
from users.managers import UserManager


class User(AbstractUser, LastModMixin, BasicModel):
    """Модель профилей"""
    REQUIRED_FIELDS = ['email']

    middle_name = models.CharField(_('Отчество'), max_length=150, blank=True, null=True)
    full_name = models.TextField(_('ФИО'), max_length=500, blank=True)
    wialon_token = models.CharField(_('Токен в Wialon'), blank=True, null=True, max_length=255)
    org_id = models.CharField(_('orgId УРА'), blank=True, null=True, max_length=255)

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
