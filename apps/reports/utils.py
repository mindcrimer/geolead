# -*- coding: utf-8 -*-
import datetime

from django.utils.timezone import get_current_timezone
from ura.models import UraJob
from ura.utils import parse_datetime


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
