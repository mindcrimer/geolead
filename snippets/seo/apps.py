# -*- coding: utf-8 -*-
from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _


class SEOConfig(AppConfig):
    name = 'snippets.seo'
    verbose_name = _('SEO')
