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
from wialon.api import get_group_object
from wialon.auth import get_wialon_session_key
from wialon.exceptions import WialonException


def get_wialon_report_object_id(user):
    name = settings.WIALON_DEFAULT_GROUP_OBJECT_NAME

    if user.wialon_group_object_name:
        name = user.wialon_group_object_name

    return get_group_object(name, user=user)


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


def get_wialon_kmu_report_template_id(user):
    return user.wialon_kmu_report_template_id \
        if user.wialon_kmu_report_template_id \
        else settings.WIALON_DEFAULT_KMU_REPORT_TEMPLATE_ID


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


def geocode(lat, lng):
    r = requests.get(
        'https://geocode-maps.yandex.ru/1.x/?geocode=%s,%s&sco=latlong&format=json&'
        'results=1&kind=house' % (lat, lng)
    )

    result = r.json()

    try:
        address = result['response']['GeoObjectCollection']['featureMember'][0]['GeoObject']
    except (KeyError, IndexError, TypeError):
        return None

    return '%s, %s' % (address['name'], address['description'])


def parse_wialon_report_datetime(str_date):
    if '-----' in str_date:
        return None

    pattern = '%Y-%m-%d %H:%M:%S' if str_date.count(':') >= 2 else '%Y-%m-%d %H:%M'
    local_dt = datetime.datetime.strptime(str_date, pattern)
    return local_dt


def utc_to_local_time(dt, timezone):
    if dt is None:
        return None

    local_dt = dt + timezone.utcoffset(dt)
    if local_dt.tzinfo is None:
        local_dt = timezone.localize(local_dt)
    return local_dt


def local_to_utc_time(dt, timezone):
    if dt is None:
        return None

    utc_dt = dt - timezone.utcoffset(datetime.datetime.now())
    if utc_dt.tzinfo is None:
        utc_dt = utc_dt.replace(tzinfo=utc)
    return utc_dt


def get_period(dt_from, dt_to, timezone=utc):
    dt_from = local_to_utc_time(dt_from, timezone)
    dt_to = local_to_utc_time(dt_to, timezone)

    dt_from = int(time.mktime(dt_from.timetuple()))
    dt_to = int(time.mktime(dt_to.timetuple()))

    return dt_from, dt_to


def cleanup_and_request_report(user, template_id, item_id=None, sess_id=None):
    if sess_id is None:
        sess_id = get_wialon_session_key(user)

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
        sess_id = get_wialon_session_key(user)

    if report_resource_id is None:
        report_resource_id = get_wialon_report_resource_id(user)

    if object_id is None:
        try:
            object_id = get_wialon_report_object_id(user)
        except WialonException:
            object_id = None

        if not object_id:
            raise ReportException(
                'Не удалось получить ID группового объекта для пользователя %s '
                '(наименование группового объекта: %s' % (
                    str(user),
                    user.wialon_group_object_name
                )
            )

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


def get_report_rows(user, table_index, rows, level=0, sess_id=None):
    if sess_id is None:
        sess_id = get_wialon_session_key(user)

    rows = requests.post(
        settings.WIALON_BASE_URL + '?svc=report/select_result_rows&sid=' +
        sess_id, {
            'params': json.dumps({
                'tableIndex': table_index,
                'config': {
                    'type': 'range',
                    'data': {
                        'from': 0,
                        'to': rows - 1,
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
