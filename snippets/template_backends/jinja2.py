# -*- coding: utf-8 -*-
import sys

from django.conf import settings
from django.contrib.staticfiles.storage import staticfiles_storage
from django.core.urlresolvers import reverse
from django.template.defaultfilters import date as date_format

import jinja2


def environment(**options):
    options.setdefault('autoescape', True)
    options.setdefault('auto_reload', settings.DEBUG)
    options.setdefault(
        'undefined',
        jinja2.DebugUndefined if settings.DEBUG else jinja2.Undefined
    )
    env = jinja2.Environment(**options)
    env.globals.update({
        'static': staticfiles_storage.url,
        'url': reverse,
        'dict': dict,
        'getattr': getattr,
        'hasattr': hasattr,
        'isinstance': isinstance,
        'str': str,
        'STATIC_URL': settings.STATIC_URL,
        'MEDIA_URL': settings.MEDIA_URL
    })
    env.filters['datetimeformat'] = date_format

    for app_label in ('snippets',) + settings.INSTALLED_APPS:
        mod_name = '.'.join((app_label, 'jinjaglobals'))
        try:
            __import__(mod_name, {}, {}, [], 0)
            mod = sys.modules[mod_name]
            for name in dir(mod):
                global_ = getattr(mod, name)
                if getattr(global_, 'is_jinja_global', False):
                    env.globals[name] = global_
                elif getattr(global_, 'is_jinja_filter', False):
                    env.filters[name] = global_
                elif getattr(global_, 'is_jinja_test', False):
                    env.tests[name] = global_
        except ImportError:
            pass

    return env


def jinjaglobal(func):
    func.is_jinja_global = True
    return func


def jinjafilter(func):
    func.is_jinja_filter = True
    return func


def jinjatest(func):
    func.is_jinja_test = True
    return func
