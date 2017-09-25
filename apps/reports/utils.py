# -*- coding: utf-8 -*-
import datetime

from django.utils.timezone import get_current_timezone

import pytz
from snippets.utils.datetime import utcnow

from ura.models import UraJob


def parse_timedelta(delta_string):
    parts = delta_string.split(':')
    delta = datetime.timedelta(seconds=0)

    for i, part in enumerate(parts):
        try:
            part = int(part)
        except ValueError:
            part = 0

        if i == 0:
            delta += datetime.timedelta(seconds=60 * 60 * part)

        elif i == 1:
            delta += datetime.timedelta(seconds=60 * part)

        elif i == 2:
            delta += datetime.timedelta(seconds=part)

    return delta


DATETIME_FORMAT = '%Y-%m-%d %H:%M'


def get_drivers_fio(units_list, unit_key, dt_from, dt_to):
    tz = get_current_timezone()

    if isinstance(dt_from, str):
        dt_from = tz.localize(datetime.datetime.strptime(dt_from, DATETIME_FORMAT))

    if isinstance(dt_to, str):
        dt_to = tz.localize(datetime.datetime.strptime(dt_to, DATETIME_FORMAT))

    unit_ids = tuple(filter(lambda x: x['name'] == unit_key, units_list))
    if not unit_ids:
        return None

    qs = UraJob.objects.filter(
        unit_id=unit_ids[0]['id'],
        date_begin__gte=dt_from,
        date_end__lte=dt_to
    )
    if qs:
        return qs[0].driver_fio

    return ''


def parse_wialon_report_datetime(str_date, timezone):
    pattern = '%Y-%m-%d %H:%M:%S' if str_date.count(':') >= 2 else '%Y-%m-%d %H:%M'
    local_dt = datetime.datetime.strptime(str_date, pattern) + \
        timezone.utcoffset(datetime.datetime.now())
    return local_dt
