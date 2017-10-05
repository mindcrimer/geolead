# -*- coding: utf-8 -*-
import datetime
import time

from django.conf import settings
from django.utils import formats
# from django.utils.timezone import template_localtime
from django.utils.dateformat import format as date_format
from reports.utils import utc_to_local_time, format_timedelta as formattimedelta

from snippets.template_backends.jinja2 import jinjafilter

@jinjafilter
def format_timedelta(value):
    return formattimedelta(value)


@jinjafilter
def date(value, arg, use_l10n=False):
    # value = template_localtime(value)
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


@jinjafilter
def render_timedelta(value):
    if not value:
        return ''

    result = str(datetime.timedelta(seconds=value))
    if 'day' in result:
        result = result.replace('days', 'day')

        try:
            days_count = int(result.split(' ')[0])
        except (ValueError, IndexError):
            days_count = 0

        if days_count:
            last_digit = int(str(days_count)[-1])
            if last_digit == 1:
                result = result.replace('day', 'день')

            elif 0 < last_digit < 5:
                result = result.replace('day', 'дня')

            else:
                result = result.replace('days', 'дней')

    return result


@jinjafilter
def render_background(value):
    if value is None:
        return '#FFF'

    if value < 10:
        return '#90EE90'

    elif value < 30:
        return '#FFFF00'

    return '#FF4500'


@jinjafilter
def utc_to_local(utc_dt, timezone):
    return utc_to_local_time(utc_dt, timezone)
