# -*- coding: utf-8 -*-
from django.db import models
from django.utils.translation import ugettext_lazy as _

from snippets.models import BaseModel
from snippets.models.enumerates import StatusEnum


class DbConfig(BaseModel):
    """Simple key-value storage in DB"""
    key = models.CharField(_('Ключ'), max_length=250, db_index=True, unique=True)
    verbose_title = models.CharField(_('Что означает'), max_length=250)
    value = models.TextField(_('Значение'), blank=True, null=False)

    translation_fields = ('value',)

    class Meta:
        verbose_name = _('Переменная')
        verbose_name_plural = _('Переменные шаблонов')

    def __str__(self):
        return '%s (%s)' % (self.key, self.verbose_title)


class Menu(BaseModel):
    """Меню"""
    slug = models.SlugField(_('Алиас'), db_index=True, unique=True)
    title = models.CharField(_('Название'), max_length=255, db_index=True, unique=True)

    def __str__(self):
        return '%s (%s)' % (self.title, self.slug)

    class Meta:
        verbose_name = _('Меню')
        verbose_name_plural = _('Меню')


class MenuItem(BaseModel):
    """Пункты меню"""
    menu = models.ForeignKey(
        Menu, related_name='items', verbose_name=_('Меню'),
        limit_choices_to={'status': StatusEnum.PUBLIC},
        on_delete=models.CASCADE
    )
    parent_item = models.ForeignKey(
        'self', related_name='children', verbose_name=_('Родительский пункт меню'),
        limit_choices_to={'status': StatusEnum.PUBLIC, 'parent_item__isnull': True},
        blank=True, null=True, on_delete=models.SET_NULL
    )
    li_class_name = models.CharField(
        _('CSS-класс (li тэг)'), blank=True, null=True, max_length=50
    )
    a_class_name = models.CharField(
        _('CSS-класс for link (a тэг)'), blank=True, null=True, max_length=50
    )
    url = models.CharField(_('Ссылка'), max_length=255)
    title = models.CharField(_('Заголовок'), max_length=255, blank=True, null=False)
    alt = models.CharField(_('Текст при наведении'), blank=True, null=True, max_length=255)

    translation_fields = ('url', 'title', 'alt')

    class Meta:
        verbose_name = _('Пункт меню')
        verbose_name_plural = _('Пункты меню')

    def __str__(self):
        return self.title
