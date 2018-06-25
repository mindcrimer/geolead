import datetime
import time

from django.conf import settings
from django.utils import formats
from django.utils.dateformat import format as date_format
from reports.utils import utc_to_local_time, format_timedelta as formattimedelta

from snippets.template_backends.jinja2 import jinjafilter, jinjaglobal


@jinjaglobal
def site_url():
    return settings.SITE_URL


@jinjafilter
def format_timedelta(value):
    return formattimedelta(value)


@jinjafilter
def date(value, arg, use_l10n=False):
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
def render_timedelta(value, default_value=''):
    if not value:
        return str(default_value)

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
                result = result.replace('day', 'дней')

    return result if result else str(default_value)


@jinjafilter
def utc_to_local(utc_dt, timezone):
    return utc_to_local_time(utc_dt, timezone)
