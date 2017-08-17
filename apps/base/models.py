# -*- coding: utf-8 -*-
from django.db import models
from django.db.models import Manager
from django.utils.translation import ugettext_lazy as _

from bs4 import BeautifulSoup
from ckeditor_uploader.fields import RichTextUploadingField
from image_cropping import ImageCropField, ImageRatioField

from snippets.models import BaseModel
from snippets.models.abstract import BaseQuerySet
from snippets.models.image import ImageMixin
from snippets.utils.datetime import utcnow


class ActualQuerySet(BaseQuerySet):
    def actual(self):
        return self.filter(publish_date__lte=utcnow())

    def not_actual(self):
        return self.filter(publish_date__gt=utcnow())


ArticleManager = Manager.from_queryset(ActualQuerySet)
ArticleManager.use_for_related_fields = True


class BaseArticle(ImageMixin, BaseModel):
    """Базовая модель для статей и новостей"""
    title = models.CharField(_('Заголовок'), max_length=255, db_index=True)
    slug = models.SlugField(
        _('Алиас'), max_length=150, db_index=True, unique=True,
        help_text=_(
            'Разрешены только латинские символы, цифры, символ подчеркивания и дефис (минус)'
        )
    )
    publish_date = models.DateTimeField(
        _('Дата публикации'), db_index=True, default=utcnow, help_text=_('Можно задать на будущее')
    )
    image = ImageCropField(
        _('Изображение'), upload_to='articles/%Y/%m/', max_length=255, blank=True, null=True
    )
    thumb_list = ImageRatioField(
        'image', '580x720', verbose_name=_('Эскиз в списке'), allow_fullsize=True, free_crop=True
    )
    thumb_siblings = ImageRatioField(
        'image', size='170x170', verbose_name=_('Эскиз в навигации'), allow_fullsize=True,
        free_crop=True
    )

    translation_fields = ('title',)
    objects = ArticleManager()

    class Meta:
        abstract = True

    def __str__(self):
        return self.title


class BaseArticleSection(BaseModel):
    """Базовый класс для секций статей"""
    title = models.CharField(_('Заголовок секции'), max_length=255, blank=True, null=True)
    body = RichTextUploadingField(
        _('Контент'), blank=True, null=False, help_text=_('Выводится выше всех секций')
    )
    gallery = models.ForeignKey(
        'core.Gallery', verbose_name=_('Галерея фотографий'), blank=True, null=True,
    )

    translation_fields = ('title', 'body')

    class Meta:
        abstract = True
        verbose_name = _('Секция статьи')
        verbose_name_plural = _('Секции статьи')

    def __str__(self):
        return str(self.pk) if self.pk else ''

    def render_body(self):
        soup = BeautifulSoup(self.body, 'lxml')
        for iframe in soup.findAll('iframe'):
            src = iframe['src']
            if 'youtube' in src:
                new_tag = BeautifulSoup(
                    '''<div class="video-preview">
                        <div class="video-preview__placeholder">
                            <span></span>
                        </div>
                        <a href="%s" class="video-preview__link"></a>
                        <div class="video-preview__iframe">
                            <div class="embed-responsive embed-responsive-16by9"></div>
                        </div>
                    </div>
                    ''' % src, 'lxml'
                )
                contents = iframe.replace_with(new_tag)
                new_tag.append(contents)

                wrap = new_tag.find_parent('p')
                if wrap:
                    wrap.unwrap()
                iframe.extract()

        return str(soup)
