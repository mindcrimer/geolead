# -*- coding: utf-8 -*-
import json

from django.utils.timezone import get_current_timezone

from django.conf import settings

import requests
from reports.utils import get_period, get_wialon_report_resource_id

from wialon.api import process_error, get_routes
from wialon.auth import get_wialon_session_key
from wialon.utils import get_wialon_tz_integer


def update_notification(request_params, user=None, sess_id=None):
    assert sess_id or user

    if sess_id is None:
        sess_id = get_wialon_session_key(user)

    r = requests.post(
        settings.WIALON_BASE_URL + '?svc=core/search_items&sid=%s' % sess_id, {
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


def create_space_overstatements_notification(job, user=None, sess_id=None, routes_cache=None):
    assert sess_id or user or job.user_id

    user = user if user else job.user
    if sess_id is None:
        sess_id = get_wialon_session_key(user)

    if not routes_cache:
        routes = get_routes(user=user, with_points=True)
        routes_cache = {r['id']: r for r in routes}

    dt_from, dt_to = get_period(job.date_begin, job.date_end, user.wialon_tz)
    route_title = routes_cache.get(int(job.route_id), {}).get('name')
    geozones = routes_cache.get(int(job.route_id), {}).get('points', [])
    geozones_ids = map(lambda x: x['id'].split('-')[1], geozones)

    data = {
        'itemId': get_wialon_report_resource_id(user),
        'id': 0,
        'callMode': 'create',
        # 'e': 1,
        'n': 'Перенахождение вне планового маршрута %s' % route_title,
        'txt': '%UNIT% находился вне планового маршрута',
        'ta': dt_from,  # время активации (UNIX формат)
        'td': dt_to,  # время деактивации (UNIX формат)
        'ma': 0,  # максимальное количество срабатываний (0 - не ограничено)
        'mmtd': 60 * 60,  # максимальный временной интервал между сообщениями (секунд)
        'cdt': 10,  # таймаут срабатывания(секунд)
        'mast': 3 * 60,  # минимальная продолжительность тревожного состояния (секунд)
        'mpst': 10,  # минимальная продолжительность предыдущего состояния (секунд)
        'cp': 24 * 60 * 60,  # период контроля относительно текущего времени (секунд)
        'fl': 2,  # флаги
        'tz': get_wialon_tz_integer(user.wialon_tz or get_current_timezone()),  # часовой пояс
        'la': 'ru',  # язык пользователя (двухбуквенный код)
        'un': [int(job.unit_id)],  # массив ID объектов/групп объектов
        'sch': {
            'f1': 0,
            'f2': 0,
            't1': 0,
            't2': 0,
            'm': 0,
            'y': 0,
            'w': 0,
            'fl': 0
        },
        'ctrl_sch': {
            'f1': 0,
            'f2': 0,
            't1': 0,
            't2': 0,
            'm': 0,
            'y': 0,
            'w': 0,
            'fl': 0
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
                'geozone_id': '1',
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
