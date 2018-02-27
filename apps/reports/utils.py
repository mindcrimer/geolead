# -*- coding: utf-8 -*-
import datetime
import json
import math
import time

from django.conf import settings
from django.utils.timezone import utc

import requests

from base.exceptions import ReportException
from reports.models import ReportLog
from reports.views.base import WIALON_INTERNAL_EXCEPTION, WIALON_SESSION_EXPIRED
from snippets.utils.datetime import utcnow
from ura.models import Job
from wialon.api import get_group_object_id, get_resource_id, get_report_template_id
from wialon.auth import get_wialon_session_key
from wialon.exceptions import WialonException


def get_wialon_report_object_id(user):
    name = settings.WIALON_DEFAULT_GROUP_OBJECT_NAME
    users_name = user.wialon_group_object_name.strip() if user.wialon_group_object_name else None

    if users_name:
        name = users_name

    return get_group_object_id(name, user=user)


def get_wialon_report_resource_id(user):
    name = user.wialon_resource_name.strip() if user.wialon_resource_name else None
    return get_resource_id(name, user=user)


def get_wialon_report_template_id(template_name, user):
    name = settings.WIALON_DEFAULT_TEMPLATE_NAMES.get(template_name)
    users_name = getattr(user, 'wialon_%s_report_template_name' % template_name)
    users_name = users_name.strip() if users_name else None

    if users_name:
        name = users_name

    return get_report_template_id(name, user)


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
        raise ReportException(
            'Не удалось найти путевой лист для получения ФИО водителя. '
            'Период: %s - %s, Название ТС: %s' % (dt_from, dt_to, unit_key)
        )

    unit_ids = tuple(filter(lambda x: x['name'] == unit_key, units_list))
    if not unit_ids:
        return None

    qs = Job.objects.filter(
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


def throttle_report(user):
    """
    Замедление выполнения отчета для прохождения лимита
    Ждем пока высвободится лимит отчетов, либо через 1 минуту выполняем в любом случае
    """
    attempts = 20
    throttle_delta = 3
    throttle_delta_cumulatime = 0

    def get_executed_reports_count(for_user):
        """
        Изучаем сколько запросов сделано за минуту
        (и на всякий случай добавим еще 5 минут)
        """
        since_dt = utcnow() - datetime.timedelta(seconds=60 + 5)
        count = ReportLog.objects.filter(user=for_user, created__gte=since_dt).count()
        # print('Reports since %s count: %s' % (since_dt, count))
        return count

    while attempts > 0 \
            and get_executed_reports_count(user) >= settings.WIALON_REPORTS_PER_MINUTE_LIMIT:
        throttle_delta_cumulatime += throttle_delta
        print('Report of user %s throttled for %s sec (attempts: %s)' % (
            user.username, throttle_delta_cumulatime, attempts
        ))
        time.sleep(throttle_delta)
        attempts -= 1

    ReportLog.objects.create(user=user)
    return True


def exec_report(user, template_id, dt_from, dt_to, report_resource_id=None, object_id=None,
                sess_id=None):
    if sess_id is None:
        sess_id = get_wialon_session_key(user)

    if report_resource_id is None:
        error = 'не выявлено'
        try:
            report_resource_id = get_wialon_report_resource_id(user)
        except WialonException as e:
            error = e

        if not report_resource_id:
            raise ReportException(
                'Не удалось получить ID ресурса для пользователя %s '
                '(наименование ресурса: %s). Ошибка: %s' % (
                    str(user),
                    user.wialon_resource_name,
                    error
                )
            )

    if object_id is None:
        error = 'не выявлено'
        try:
            object_id = get_wialon_report_object_id(user)
        except WialonException as e:
            error = e

        if not object_id:
            raise ReportException(
                'Не удалось получить ID группового объекта для пользователя %s '
                '(наименование группового объекта: %s). Ошибка: %s' % (
                    str(user),
                    user.wialon_group_object_name,
                    error
                )
            )

    # замедляем в случае чего, для прохождения лимита
    throttle_report(user)

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
        if result['error'] == 1:
            raise ReportException(WIALON_SESSION_EXPIRED)
        raise ReportException(WIALON_INTERNAL_EXCEPTION % result)

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
        if rows['error'] == 1:
            raise ReportException(WIALON_SESSION_EXPIRED)
        raise ReportException(WIALON_INTERNAL_EXCEPTION % rows)

    return rows
