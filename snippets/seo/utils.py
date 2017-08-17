# -*- coding: utf-8 -*-
import sys

import collections
from django.conf import settings


def collect_sitemap_urls():
    urls = []
    for app_label in settings.INSTALLED_APPS:
        mod_name = '.'.join((app_label, 'pages'))
        try:
            __import__(mod_name, {}, {}, [], 0)
            mod = sys.modules[mod_name]
            names = dir(mod)
            if 'get_page_urls' in names:
                global_func = mod.get_page_urls
                for lang in settings.LANGUAGE_CODES_PUBLIC:
                    result = global_func(lang)
                    if result and isinstance(result, collections.Iterable):
                        urls.extend(tuple(result))
        except ImportError:
            pass

    return urls
