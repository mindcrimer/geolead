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
    email_verified_date = models.DateTimeField(
        _('Дата и время подтверждения email'), blank=True, null=True
    )

    restore_salt = models.CharField(
        _('Соль восстановления пароля'), max_length=50,
        help_text=_(
            'Выставляется при запросе восстановления пароля и удаляется '
            'после успешной смены пароля, либо по сроку годности'
        ),
        blank=True, null=True
    )
    restore_salt_expiry = models.DateTimeField(
        _('Срок годности соли восстановления'), blank=True, null=True
    )

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
