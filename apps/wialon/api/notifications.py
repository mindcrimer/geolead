# -*- coding: utf-8 -*-
import json
import time

from django.utils.timezone import get_current_timezone

from django.conf import settings

import requests

from notifications.exceptions import NotificationError
from reports.utils import get_wialon_report_resource_id

from wialon.api import process_error, get_routes
from wialon.auth import get_wialon_session_key
from wialon.utils import get_wialon_tz_integer


def remove_notification(notification, user=None, sess_id=None):
    assert sess_id or user

    if sess_id is None:
        sess_id = get_wialon_session_key(user)

    r = requests.post(
        settings.WIALON_BASE_URL + '?svc=resource/update_notification&sid=%s' % sess_id, {
            'params': json.dumps({
                'itemId': get_wialon_report_resource_id(user),
                'id': notification.wialon_id,
                'callMode': 'delete',
            }),
            'sid': sess_id
        }
    )
    res = r.json()
    process_error(
        res, 'Не удалось удалить шаблон уведомлений ID="%s"' % notification.pk
    )

    return res


def update_notification(request_params, user=None, sess_id=None):
    assert sess_id or user

    if sess_id is None:
        sess_id = get_wialon_session_key(user)

    r = requests.post(
        settings.WIALON_BASE_URL + '?svc=resource/update_notification&sid=%s' % sess_id, {
            'params': json.dumps(request_params),
            'sid': sess_id
        }
    )
    res = r.json()
    action = 'сохранить'
    if request_params.get('callMode', '') == 'delete':
        action = 'удалить'

    process_error(
        res, ('Не удалось %s шаблон уведомлений "%s"' % (action, request_params.get('n', '')))
    )

    return res


def create_space_overstatements_notification(job, user=None, sess_id=None, routes_cache=None,
                                             job_template=None):
    """Перенахождение вне планового маршрута"""
    assert sess_id or user or job.user_id

    if not job_template or not job_template.space_overstatements_standard:
        raise NotificationError(
            'Не найден норматив перенахождения вне маршрута. ID ПЛ=%s' % job.pk
        )

    user = user if user else job.user
    if sess_id is None:
        sess_id = get_wialon_session_key(user)

    if not routes_cache:
        routes = get_routes(user=user, with_points=True)
        routes_cache = {r['id']: r for r in routes}

    dt_from = int(time.mktime(job.date_begin.timetuple()))
    dt_to = int(time.mktime(job.date_end.timetuple()))

    route = routes_cache.get(int(job.route_id), {})
    route_title = route.get('name')
    geozones = route.get('points', [])
    geozones_ids = list(map(lambda x: x['id'].split('-')[1], geozones))

    if not route or not geozones:
        raise NotificationError('Маршрут неизвестен или отсутствуют геозоны. ID ПЛ=%s' % job.pk)

    data = {
        'itemId': get_wialon_report_resource_id(user),
        'id': 0,
        'callMode': 'create',
        'n': 'Перенахождение вне планового маршрута %s' % route_title,
        'txt': '%UNIT% находился вне планового маршрута',
        # время активации (UNIX формат)
        'ta': dt_from,
        # время деактивации (UNIX формат)
        'td': dt_to,
        # максимальное количество срабатываний (0 - не ограничено)
        'ma': 0,
        # таймаут срабатывания(секунд)
        'cdt': 10,
        # максимальный временной интервал между сообщениями (секунд)
        'mmtd': 60 * 60,
        # минимальная продолжительность тревожного состояния (секунд)
        'mast': int(job_template.space_overstatements_standard * 60.0),
        # минимальная продолжительность предыдущего состояния (секунд)
        'mpst': 10,
        # период контроля относительно текущего времени (секунд)
        'cp': 24 * 60 * 60,
        # флаги
        'fl': 0,
        # часовой пояс
        'tz': get_wialon_tz_integer(user.wialon_tz or get_current_timezone()),
        # язык пользователя (двухбуквенный код)
        'la': 'ru',
        # массив ID объектов/групп объектов
        'un': [int(job.unit_id)],
        'sch': {
            'f1': 0,
            'f2': 0,
            't1': 0,
            't2': 0,
            'm': 0,
            'y': 0,
            'w': 0
        },
        'ctrl_sch': {
            'f1': 0,
            'f2': 0,
            't1': 0,
            't2': 0,
            'm': 0,
            'y': 0,
            'w': 0
        },
        'trg': {
            't': 'geozone',
            'p': {
                'sensor_type': '',
                'sensor_name_mask': '',
                'lower_bound': 0,
                'upper_bound': 0,
                'merge': 0,
                'geozone_ids': ','.join(geozones_ids),
                'reversed': 0,
                'type': 1,
                'min_speed': 0,
                'max_speed': 0,
                'lo': 'AND'
            }
        },
        'act': [
            {
                't': 'message',
                'p': {
                    'name': 'Перенахождение вне планового маршрута %s' % route_title,
                    'url': '',
                    'color': '',
                    'blink': 0
                }
            }, {
                't': 'event',
                'p': {
                    'flags': 1
                }
            }
        ]
    }

    result = update_notification(data, user=user, sess_id=sess_id)
    return result[0], result[1], data
