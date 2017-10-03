# -*- coding: utf-8 -*-
import datetime
import json
import math
import time

from django.conf import settings
from django.utils.timezone import utc

import requests

from base.exceptions import ReportException
from reports.views.base import WIALON_INTERNAL_EXCEPTION
from ura.models import UraJob
from ura.wialon.auth import authenticate_at_wialon


def get_wialon_report_object_id(user):
    return user.wialon_report_object_id \
        if user.wialon_report_object_id \
        else settings.WIALON_REPORTS_DEFAULT_OBJECT_ID


def get_wialon_report_resource_id(user):
    return user.wialon_report_resource_id \
        if user.wialon_report_resource_id \
        else settings.WIALON_DEFAULT_REPORT_RESOURCE_ID


def get_wialon_discharge_report_template_id(user):
    return user.wialon_discharge_report_template_id \
        if user.wialon_discharge_report_template_id \
        else settings.WIALON_DEFAULT_DISCHARGE_REPORT_TEMPLATE_ID


def get_wialon_driving_style_report_template_id(user):
    return user.wialon_driving_style_report_template_id \
        if user.wialon_driving_style_report_template_id \
        else settings.WIALON_DEFAULT_DRIVING_STYLE_REPORT_TEMPLATE_ID


def get_wialon_geozones_report_template_id(user):
    return user.wialon_geozones_report_template_id \
        if user.wialon_geozones_report_template_id \
        else settings.WIALON_DEFAULT_GEOZONES_REPORT_TEMPLATE_ID


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


def format_timedelta(seconds):
    hours = math.floor(seconds / 3600)
    rest = seconds - (3600 * hours)

    minutes = math.floor(rest / 60)
    secs = rest - (60 * minutes)

    return '%s:%s:%s' % tuple(str(x).rjust(2, '0') for x in (hours, minutes, secs))


DATETIME_FORMAT = '%Y-%m-%d %H:%M'


def get_drivers_fio(units_list, unit_key, dt_from, dt_to, timezone):
    try:
        if isinstance(dt_from, str):
            dt_from = local_to_utc_time(parse_wialon_report_datetime(dt_from), timezone)

        if isinstance(dt_to, str):
            dt_to = local_to_utc_time(parse_wialon_report_datetime(dt_to), timezone)
    except ValueError:
        raise ReportException('Ошибка получения данных. Повторите запрос.')

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


def parse_wialon_report_datetime(str_date):
    pattern = '%Y-%m-%d %H:%M:%S' if str_date.count(':') >= 2 else '%Y-%m-%d %H:%M'
    local_dt = datetime.datetime.strptime(str_date, pattern)
    return local_dt


def utc_to_local_time(dt, timezone):
    local_dt = dt + timezone.utcoffset(datetime.datetime.now())
    if local_dt.tzinfo is None:
        local_dt = local_dt.replace(tzinfo=timezone)
    return local_dt


def local_to_utc_time(dt, timezone):
    utc_dt = dt - timezone.utcoffset(datetime.datetime.now())
    if utc_dt.tzinfo is None:
        utc_dt = utc_dt.replace(tzinfo=utc)
    return utc_dt


def get_period(dt_from, dt_to, timezone):
    dt_from = local_to_utc_time(dt_from, timezone)
    dt_to = local_to_utc_time(dt_to, timezone)

    dt_from = int(time.mktime(dt_from.timetuple()))
    dt_to = int(time.mktime(dt_to.timetuple()))

    return dt_from, dt_to


def cleanup_and_request_report(user, template_id, item_id=None, sess_id=None):
    if sess_id is None:
        sess_id = authenticate_at_wialon(user.wialon_token)

    if item_id is None:
        item_id = get_wialon_report_resource_id(user)

    requests.post(
        settings.WIALON_BASE_URL + '?svc=core/batch&sid=' + sess_id, {
            'params': json.dumps({
                'params': [
                    {
                        'svc': 'report/cleanup_result',
                        'params': {}
                    },
                    {
                        'svc': 'report/get_report_data',
                        'params': {
                            'itemId': item_id,
                            'col': [str(template_id)],
                            'flags': 0
                        }
                    }
                ],
                'flags': 0
            }),
            'sid': sess_id
        }
    )


def exec_report(user, template_id, dt_from, dt_to, report_resource_id=None, object_id=None,
                sess_id=None):
    if sess_id is None:
        sess_id = authenticate_at_wialon(user.wialon_token)

    if report_resource_id is None:
        report_resource_id = get_wialon_report_resource_id(user)

    if object_id is None:
        object_id = get_wialon_report_object_id(user)

    r = requests.post(
        settings.WIALON_BASE_URL + '?svc=report/exec_report&sid=' + sess_id, {
            'params': json.dumps({
                'reportResourceId': report_resource_id,
                'reportTemplateId': template_id,
                'reportTemplate': None,
                'reportObjectId': object_id,
                'reportObjectSecId': 0,
                'interval': {
                    'flags': 0,
                    'from': dt_from,
                    'to': dt_to
                }
            }),
            'sid': sess_id
        }
    )

    result = r.json()

    if 'error' in result:
        raise ReportException(WIALON_INTERNAL_EXCEPTION)

    return result


def get_report_rows(user, table_index, table_info, level=0, sess_id=None):
    if sess_id is None:
        sess_id = authenticate_at_wialon(user.wialon_token)

    rows = requests.post(
        settings.WIALON_BASE_URL + '?svc=report/select_result_rows&sid=' +
        sess_id, {
            'params': json.dumps({
                'tableIndex': table_index,
                'config': {
                    'type': 'range',
                    'data': {
                        'from': 0,
                        'to': table_info['rows'] - 1,
                        'level': level
                    }
                }
            }),
            'sid': sess_id
        }
    ).json()

    if 'error' in rows:
        raise ReportException(WIALON_INTERNAL_EXCEPTION)

    return rows