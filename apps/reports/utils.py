import datetime
import json
import math
import time

from django.conf import settings
from django.utils.timezone import utc

import requests

from base.exceptions import ReportException
from reports.models import WialonReportLog
from reports.views.base import WIALON_INTERNAL_EXCEPTION, WIALON_SESSION_EXPIRED
from simplejson import JSONDecodeError
from snippets.utils.datetime import utcnow
from wialon.api import get_group_object_id, get_resource_id, get_report_template_id
from wialon.auth import get_wialon_session_key, logout_session
from wialon.exceptions import WialonException
from wialon.utils import load_requests_json


def get_wialon_report_object_id(user, sess_id):
    name = settings.WIALON_DEFAULT_GROUP_OBJECT_NAME
    users_name = user.wialon_group_object_name.strip() if user.wialon_group_object_name else None

    if users_name:
        name = users_name

    return get_group_object_id(name, user, sess_id)


def get_wialon_report_resource_id(user, sess_id):
    name = user.wialon_resource_name.strip() if user.wialon_resource_name else None
    return get_resource_id(name, user, sess_id)


def get_wialon_report_template_id(template_name, user, sess_id):
    name = settings.WIALON_DEFAULT_TEMPLATE_NAMES.get(template_name)
    users_name = getattr(user, 'wialon_%s_report_template_name' % template_name)
    users_name = users_name.strip() if users_name else None

    if users_name:
        name = users_name

    return get_report_template_id(name, user, sess_id)


def parse_timedelta(delta_string):
    delta = datetime.timedelta(seconds=0)

    if '-' in delta_string or not delta_string:
        return delta

    day_parts = delta_string.strip().split(' ')
    if len(day_parts) >= 2:
        if len(day_parts) > 2:
            del day_parts[1]
        try:
            delta += datetime.timedelta(days=int(day_parts[0]))
        except ValueError:
            pass
        delta_string = day_parts[1]

    parts = delta_string.strip().split(':')

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
    hours = int(math.floor(seconds / 3600))
    rest = seconds - (3600 * hours)

    minutes = int(math.floor(rest / 60))
    secs = rest - (60 * minutes)

    return '%s:%s:%s' % (
        str(hours),
        str(minutes).rjust(2, '0'),
        str(int(secs)).rjust(2, '0')
    )


DATETIME_FORMAT = '%Y-%m-%d %H:%M'


def parse_address(row):
    if isinstance(row, dict):
        address = row.get('t', '---')
    else:
        address = str(row)

    return address if '---' not in address else None


def parse_coords(row):
    if isinstance(row, dict) and row.get('x') and row.get('y'):
        return {
            'lat': row.get('y'),
            'lng': row.get('x')
        }
    return None


def parse_wialon_report_datetime(str_date):
    if not str_date:
        return None

    if isinstance(str_date, dict):
        str_date = str_date['t']

    str_date = str_date.lower().strip()
    if any([(str_date in x) for x in ('-----', 'неизвестно', 'unknown')]):
        return None

    pattern = '%Y-%m-%d %H:%M:%S' if str_date.count(':') >= 2 else '%Y-%m-%d %H:%M'
    local_dt = datetime.datetime.strptime(str_date, pattern)
    return local_dt


def utc_to_local_time(dt, timezone):
    if dt is None:
        return None

    if dt.tzinfo is not None:
        dt = dt.replace(tzinfo=None)

    local_dt = dt + timezone.utcoffset(dt)
    # if local_dt.tzinfo is None:
    #     local_dt = timezone.localize(local_dt)
    return local_dt


def local_to_utc_time(dt, timezone):
    if dt is None:
        return None

    utc_dt = dt - timezone.utcoffset(datetime.datetime.now())
    # if utc_dt.tzinfo is None:
    utc_dt = utc_dt.replace(tzinfo=utc)
    return utc_dt


def get_period(dt_from, dt_to, timezone=utc):
    dt_from = local_to_utc_time(dt_from, timezone)
    dt_to = local_to_utc_time(dt_to, timezone)

    dt_from = int(time.mktime(dt_from.timetuple()))
    dt_to = int(time.mktime(dt_to.timetuple()))

    return dt_from, dt_to


def cleanup_and_request_report(user, template_id, sess_id, item_id=None):
    if item_id is None:
        item_id = get_wialon_report_resource_id(user, sess_id)

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
    attempts = int(
        settings.WIALON_REPORTS_EXECUTE_ANYWAY_AFTER / settings.WIALON_REPORTS_THROTTLE_TIME
    )
    throttle_delta_cumulatime = 0

    def get_executed_reports_count(for_user):
        """
        Изучаем сколько запросов сделано за минуту
        (и на всякий случай добавим еще 5 минут)
        """
        since_dt = utcnow() - datetime.timedelta(seconds=settings.WIALON_REPORTS_LIMIT_PERIOD)
        count = WialonReportLog.objects.filter(user=for_user, created__gte=since_dt).count()
        return count

    while attempts > 0 \
            and get_executed_reports_count(user) >= settings.WIALON_REPORTS_PER_PERIOD_LIMIT:
        throttle_delta_cumulatime += settings.WIALON_REPORTS_THROTTLE_TIME
        print('Report of user %s was throttled for %s sec (attempts: %s)' % (
            user.username, throttle_delta_cumulatime, attempts
        ))
        time.sleep(settings.WIALON_REPORTS_THROTTLE_TIME)
        attempts -= 1

    WialonReportLog.objects.create(user=user)
    return True


def exec_report(user, template_id, sess_id, dt_from, dt_to, report_resource_id=None,
                object_id=None, attempts=3):

    if report_resource_id is None:
        error = 'не выявлено'
        try:
            report_resource_id = get_wialon_report_resource_id(user, sess_id)
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
            object_id = get_wialon_report_object_id(user, sess_id)
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

    result = load_requests_json(r)

    if 'error' in result:
        # сессия неожиданно устарела (такое очень редко и необъяснимо бывает) - отправляем еще раз
        if result['error'] == 1:
            if attempts > 1:
                # генерируем новую сессию
                sess_id = get_wialon_session_key(user, invalidate=True)
                result = exec_report(
                    user, template_id, sess_id, dt_from, dt_to,
                    report_resource_id=report_resource_id,
                    object_id=object_id,
                    attempts=attempts - 1
                )
                logout_session(user, sess_id)
                return result

            raise ReportException(WIALON_SESSION_EXPIRED)
        raise ReportException(WIALON_INTERNAL_EXCEPTION % result)

    return result


def get_report_rows(sess_id, table_index, rows, offset=0, level=0):

    result = requests.post(
        settings.WIALON_BASE_URL + '?svc=report/select_result_rows&sid=' +
        sess_id, {
            'params': json.dumps({
                'tableIndex': table_index,
                'config': {
                    'type': 'range',
                    'data': {
                        'from': offset,
                        'to': rows - 1,
                        'level': level
                    }
                }
            }),
            'sid': sess_id
        }
    )

    try:
        rows = load_requests_json(result)
    except JSONDecodeError:
        raise ReportException('Ошибка раскодирования ответа Wialon: %s' % result.text)

    if 'error' in rows:
        if rows['error'] == 1:
            raise ReportException(WIALON_SESSION_EXPIRED)
        raise ReportException(WIALON_INTERNAL_EXCEPTION % rows)

    return rows
