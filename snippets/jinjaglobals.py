# -*- coding: utf-8 -*-
import os
import random
import re
import time

from django.conf import settings
from django.contrib.humanize.templatetags.humanize import intcomma as int_comma
from django.template.defaultfilters import floatformat as float_format
from django.utils import formats
from django.utils.dateformat import format as date_format
from django.utils.timezone import template_localtime
from django.utils.translation import ugettext_lazy as _

from easy_thumbnails.conf import settings as thumbnailer_settings
from easy_thumbnails.exceptions import InvalidImageFormatError
from easy_thumbnails.files import get_thumbnailer
from easy_thumbnails.templatetags.thumbnail import RE_SIZE, VALID_OPTIONS
from jinja2 import nodes
from jinja2.exceptions import TemplateSyntaxError
from jinja2.ext import Extension
from markupsafe import escape

from snippets.db_config import db_vars
from snippets.template_backends.jinja2 import jinjaglobal, jinjafilter


class SpacelessExtension(Extension):
    """
    Removes whitespace between HTML tags at compile time, including tab and newline characters.
    It does not remove whitespace between jinja2 tags or variables.
    Neither does it remove whitespace between tags and their text content.
    Adapted from coffin:
        https://github.com/coffin/coffin/blob/master/coffin/template/defaulttags.py
    """
    tags = {'spaceless'}

    def parse(self, parser):
        lineno = parser.stream.next().lineno
        body = parser.parse_statements(['name:endspaceless'], drop_needle=True)
        return nodes.CallBlock(
            self.call_method('_strip_spaces', [], [], None, None),
            [], [], body,
        ).set_lineno(lineno)

    def _strip_spaces(self, caller=None):
        return re.sub(r'>\s+<', '><', caller().strip())


class CacheExtension(Extension):
    """Exactly like Django's own tag, but supports full Jinja2
    expressiveness for all arguments.

        {% cache gettimeout()*2 "foo"+options.cachename  %}
            ...
        {% endcache %}

    This actually means that there is a considerable incompatibility
    to Django: In Django, the second argument is simply a name, but
    interpreted as a literal string. This tag, with Jinja2 stronger
    emphasis on consistent syntax, requires you to actually specify the
    quotes around the name to make it a string. Otherwise, allowing
    Jinja2 expressions would be very hard to impossible (one could use
    a lookahead to see if the name is followed by an operator, and
    evaluate it as an expression if so, or read it as a string if not.
    TODO: This may not be the right choice. Supporting expressions
    here is probably not very important, so compatibility should maybe
    prevail. Unfortunately, it is actually pretty hard to be compatibly
    in all cases, simply because Django's per-character parser will
    just eat everything until the next whitespace and consider it part
    of the fragment name, while we have to work token-based: ``x*2``
    would actually be considered ``"x*2"`` in Django, while Jinja2
    would give us three tokens: ``x``, ``*``, ``2``.

    General Syntax:

        {% cache [expire_time] [fragment_name] [var1] [var2] .. %}
            .. some expensive processing ..
        {% endcache %}

    Available by default (does not need to be loaded).

    Partly based on the ``FragmentCacheExtension`` from the Jinja2 docs.

    TODO: Should there be scoping issues with the internal dummy macro
    limited access to certain outer variables in some cases, there is a
    different way to write this. Generated code would look like this:

        internal_name = environment.extensions['..']._get_cache_value():
        if internal_name is not None:
            yield internal_name
        else:
            internal_name = ""  # or maybe use [] and append() for performance
            internalname += "..."
            internalname += "..."
            internalname += "..."
            environment.extensions['..']._set_cache_value(internalname):
            yield internalname

    In other words, instead of using a CallBlock which uses a local
    function and calls into python, we have to separate calls into
    python, but put the if-else logic itself into the compiled template.
    """
    tags = {'cache'}

    def parse(self, parser):
        lineno = parser.stream.next().lineno

        expire_time = parser.parse_expression()
        fragment_name = parser.parse_expression()
        vary_on = []
        while not parser.stream.current.test('block_end'):
            vary_on.append(parser.parse_expression())

        body = parser.parse_statements(['name:endcache'], drop_needle=True)

        return nodes.CallBlock(
            self.call_method('_cache_support',
                             [expire_time, fragment_name,
                              nodes.List(vary_on), nodes.Const(lineno)]),
            [], [], body).set_lineno(lineno)

    def _cache_support(self, expire_time, fragm_name, vary_on, lineno, caller):
        from hashlib import md5
        from django.core.cache import cache   # delay depending in settings
        from django.utils.http import urlquote

        try:
            expire_time = int(expire_time)
        except (ValueError, TypeError):
            raise TemplateSyntaxError(
                '"%s" tag got a non-integer timeout value: %r' % (list(self.tags)[0], expire_time),
                lineno
            )

        args_string = ':'.join([urlquote(v) for v in vary_on])
        args_md5 = md5(args_string)
        cache_key = 'template.cache.%s.%s' % (fragm_name, args_md5.hexdigest())
        value = cache.get(cache_key)
        if value is None:
            value = caller()
            cache.set(cache_key, value, expire_time)
        return value


@jinjafilter
def cropped_thumbnail(instance, field_name, width=None, height=None, scale=None, **opts):
    """Cropper"""
    ratiofield = instance._meta.get_field(field_name)
    image = getattr(instance, ratiofield.image_field)
    if ratiofield.image_fk_field:
        image = getattr(image, ratiofield.image_fk_field)
    if not image:
        return ''

    size = (int(ratiofield.width), int(ratiofield.height))
    box = getattr(instance, field_name)

    if scale:
        scale = float(scale)
        width = size[0] * scale
        height = size[1] * scale
    elif width and height:
        width = float(width)
        h = size[1] * width / size[0]
        if h > height:
            width = height * size[0] / size[1]
        else:
            height = h
    elif width:
        width = float(width)
        height = size[1] * width / size[0]
    elif height:
        height = float(height)
        width = height * size[0] / size[1]

    if width and height:
        size = (int(width), int(height))

    if ratiofield.adapt_rotation:
        if (image.height > image.width) != (size[1] > size[0]):
            size = (size[1], size[0])

    thumbnailer = get_thumbnailer(image)
    thumbnail_options = {
        'size': size,
        'box': box,
        **opts
    }
    try:
        return thumbnailer.get_thumbnail(thumbnail_options).url
    except InvalidImageFormatError:
        return ''


@jinjafilter
def date(value, arg, use_l10n=True):
    value = template_localtime(value)
    if value in (None, ''):
        return ''
    if arg is None:
        arg = settings.DATE_FORMAT
    if arg == 'timestamp':
        return str(int(time.mktime(value.timetuple())))
    try:
        return formats.date_format(value, arg, use_l10n=use_l10n)
    except AttributeError:
        try:
            return date_format(value, arg)
        except AttributeError:
            return ''


@jinjaglobal
def get_language_href(request, lang):
    url = request.get_full_path()

    parts = url.split('/')
    parts[1] = lang
    url = '/'.join(parts)
    return url if url.endswith('/') else url + '/'


@jinjaglobal
def get_languages():
    return [x for x in settings.LANGUAGES if x[0] in settings.LANGUAGE_CODES_PUBLIC]


@jinjafilter
def floatformat(value, digits):
    """Порт floatformat"""
    return float_format(value, digits)


@jinjafilter
def floatcomma(value, digits):
    return float_format(value, digits).replace(',', '.')



@jinjafilter
def intcomma(value, use_l10n=True):
    return int_comma(value, use_l10n=use_l10n)


phone_re = re.compile(r'(\.|\s|-|\)|\()+')


@jinjafilter
def phone_url(val):
    val = strip_whitescapes(val, phone_re)

    # если не 8 800
    if not val.startswith('8'):
        if not val.startswith('+'):
            val = '+7' + val

    return val


@jinjaglobal
def random_int():
    return random.randint(1, 9999999)


@jinjafilter
def rjust(value, width, fillchar):
    return str(value).rjust(width, fillchar)


@jinjaglobal
def site_name():
    return settings.SITE_NAME


@jinjaglobal
def site_url():
    return settings.SITE_URL


@jinjaglobal
def static_with_mtime(file_path):
    filemtime = int(
        os.path.getmtime(os.path.join(settings.STATIC_ROOT, file_path))
    )
    return '%s%s?v=%s' % (settings.STATIC_URL, file_path, filemtime)


whitespace_re = re.compile(r'(\s|-|\)|\()+', re.MULTILINE)


@jinjafilter
def strip_whitescapes(val, re_obj=whitespace_re):
    return re_obj.sub('', val)


@jinjafilter
def thumbnail_obj(source, size, **opts):
    """Make thumbnail from source image"""
    if not source:
        return None

    raise_errors = thumbnailer_settings.THUMBNAIL_DEBUG
    accepted_opts = {}
    for key, value in opts.items():
        if key in VALID_OPTIONS:
            accepted_opts[key] = value
    opts = accepted_opts
    m = RE_SIZE.match(size)

    if m:
        opts['size'] = (int(m.group(1)), int(m.group(2)))
    else:
        if raise_errors:
            raise TemplateSyntaxError('%r is not a valid size.' % size, 1)

    if 'quality' in opts:
        try:
            opts['quality'] = int(opts['quality'])
        except (TypeError, ValueError):
            if raise_errors:
                raise TemplateSyntaxError('%r is an invalid quality.' % opts['quality'], 1)

    try:
        curr_thumbnail = get_thumbnailer(source).get_thumbnail(opts)
    except Exception as e:
        if raise_errors:
            raise TemplateSyntaxError('Couldn\'t get the thumbnail %s: %s' % (source, e), 1)
        else:
            return None

    return curr_thumbnail


@jinjafilter
def thumbnail(source, size, **opts):
    thumb = thumbnail_obj(source, size, **opts)
    return escape(thumb.url) if thumb else ''


@jinjaglobal
def ugettext(value):
    return _(value)


@jinjaglobal
def var(key, request, **kwargs):
    result = db_vars.get(key, request.LANGUAGE_CODE, '')
    if kwargs:
        result = result.format(**kwargs)
    return result
