# -*- coding: utf-8 -*-
from django.db import models
from django.utils.translation import ugettext_lazy as _

from snippets.models import BaseModel, BaseManager
from snippets.seo.enums import RedirectCodesEnum


class SEOMixin(models.Model):
    """Базовый класс для SEO-параметров модели"""
    seo_title = models.CharField(_('SEO Заголовок (title)'), max_length=254, blank=True, null=True)
    seo_description = models.TextField(_('META Description'), blank=True, null=True)
    seo_keywords = models.TextField(_('META Keywords'), blank=True, null=True)

    translation_fields = ('seo_title', 'seo_description', 'seo_keywords')

    def collect_fieldsets(self, extra_general=None):
        fields = self.collect_fields()
        if extra_general:
            fields += extra_general
        return [
            (_('Основное'), {
                'classes': ('suit-tab suit-tab-general',),
                'fields': fields
            }),
            ('SEO', {
                'classes': ('suit-tab suit-tab-seo',),
                'fields': ['seo_title', 'seo_description', 'seo_keywords']
            }),
        ]

    def apply_seo_params(self, request):
        request.seo_params = {
            'seo_title': self.seo_title,
            'seo_description': self.seo_description,
            'seo_keywords': self.seo_keywords,
        }
        return request

    class Meta:
        abstract = True


class SEOPage(SEOMixin, BaseModel):
    """SEO properties"""
    url = models.CharField(
        _('Ссылка (URL)'), max_length=255, blank=True, null=False,
        db_index=True, unique=True,
        help_text=_(
            'Введите URL страницы, параметры которой хотите переопределить, '
            'без указания домена и языка! Например, /about/'
        )
    )

    def __str__(self):
        return '%s: %s' % (self.url, self.seo_title)

    class Meta:
        verbose_name = _('SEO параметр')
        verbose_name_plural = _('SEO параметры')


class Redirect(BaseModel):
    """Location redirects"""
    old_path = models.TextField(_('Откуда'), max_length=1024, db_index=True, unique=True)
    new_path = models.TextField(_('Куда'), max_length=1024)
    http_code = models.PositiveIntegerField(
        _('Код состояния'), choices=RedirectCodesEnum.get_choices(), default=RedirectCodesEnum.C301
    )
    objects = BaseManager()

    def save(self, *args, **kwargs):
        result = super(Redirect, self).save(*args, **kwargs)
        from snippets.seo.router import router
        router.index()
        return result

    def __str__(self):
        return '%s: %s => %s' % (
            RedirectCodesEnum.values[self.http_code],
            self.old_path,
            self.new_path,
        )

    class Meta:
        verbose_name = _('Редирект')
        verbose_name_plural = _('Редиректы')


class Robot(BaseModel):
    """Робот для robots.txt"""
    title = models.CharField(_('Имя робота'), max_length=254, blank=False, null=False)
    host = models.CharField(_('Host'), max_length=254, blank=True, null=True)
    crawl_delay = models.DecimalField(
        _('Crawl-delay'), blank=True, null=True, decimal_places=1, max_digits=5
    )
    objects = BaseManager()

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = _('Робот (User-agent)')
        verbose_name_plural = _('Robots.txt')


class RobotDisallow(BaseModel):
    """Строка запрета для робота"""
    robot = models.ForeignKey(
        Robot, verbose_name=_('Робот'), blank=False, null=False, related_name='disallows'
    )
    url_pattern = models.CharField(_('Шаблон (ссылка)'), max_length=254, blank=False, null=False)
    objects = BaseManager()

    class Meta:
        verbose_name = _('Disallow')
        verbose_name_plural = _('Disallow (Запреты)')


class RobotAllow(BaseModel):
    """Строка разрешения для робота"""
    robot = models.ForeignKey(
        Robot, verbose_name=_('Робот'), blank=False, null=False, related_name='allows'
    )
    url_pattern = models.CharField(_('Шаблон ссылки'), max_length=254, blank=False, null=False)
    objects = BaseManager()

    class Meta:
        verbose_name = _('Allow')
        verbose_name_plural = _('Allow (Разрешения)')


class RobotCleanparam(BaseModel):
    """Строка Clean-param для робота"""
    robot = models.ForeignKey(
        Robot, verbose_name=_('Робот'), blank=False, null=False, related_name='clean_params'
    )
    params = models.CharField(_('Параметры'), max_length=254, blank=False, null=False)
    url_pattern = models.CharField(_('Шаблон ссылки'), max_length=254, blank=False, null=False)
    objects = BaseManager()

    class Meta:
        verbose_name = _('Clean-param')
        verbose_name_plural = _('Параметры Clean-param')


class RobotSitemap(BaseModel):
    """Строка Sitemap для робота"""
    robot = models.ForeignKey(
        Robot, verbose_name=_('Робот'), blank=False, null=False, related_name='sitemaps'
    )
    url = models.CharField(_('Sitemap'), max_length=254, blank=False, null=False)
    objects = BaseManager()

    class Meta:
        verbose_name = _('Sitemap')
        verbose_name_plural = _('Sitemap (Карты сайта XML)')
