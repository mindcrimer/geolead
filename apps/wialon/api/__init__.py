# -*- coding: utf-8 -*-
import json
from smtplib import SMTPException

from django.conf import settings
from django.core.cache import cache

import requests
from snippets.utils.email import send_trigger_email

from wialon import DEFAULT_CACHE_TIMEOUT
from wialon.exceptions import WialonException
from wialon.auth import get_wialon_session_key


def process_error(result, error):
    if 'error' in result:
        if result['error'] == 1:
            raise WialonException(
                error + ' Ошибка: ваша сессия устарела. Зайдите заново в приложение через APPS.'
            )
        raise WialonException(error + (' Ошибка: %s' % result))


def get_drivers(user=None, sess_id=None):
    """Получает список водителей"""
    assert user or sess_id

    if sess_id is None:
        sess_id = get_wialon_session_key(user)

    cache_key = 'drivers:%s' % sess_id
    drivers_list = cache.get(cache_key)

    if drivers_list:
        return json.loads(drivers_list)

    request_params = json.dumps({
        'spec': {
            'itemsType': 'avl_resource',
            'propName': 'drivers',
            'propValueMask': '*',
            'sortType': 'drivers',
            'propType': 'propitemname'
        },
        'force': 1,
        'flags': 1 + 256,
        'from': 0,
        'to': 0
    })
    r = requests.get(
        settings.WIALON_BASE_URL + (
                '?svc=core/search_items&params=%s&sid=%s' % (request_params, sess_id)
        )
    )
    res = r.json()

    process_error(res, 'Не удалось извлечь из Wialon список водителей.')

    drivers = []
    for item in res['items']:
        if item and item['drvrs']:
            drivers.extend([{
                'id': '%s-%s' % (item['id'], x['id']),
                'name': x['n']
            } for x in item['drvrs'].values()])

    if DEFAULT_CACHE_TIMEOUT:
        cache.set(cache_key, json.dumps(drivers), DEFAULT_CACHE_TIMEOUT)

    return drivers


def get_group_object_id(name, user=None, sess_id=None):
    """Получает ID группового объекта"""
    assert user or sess_id

    if sess_id is None:
        sess_id = get_wialon_session_key(user)

    request_params = json.dumps({
        'spec': {
            'itemsType': 'avl_unit_group',
            'propName': 'sys_name',
            'propValueMask': name,
            'sortType': 'sys_name',
            'propType': 'property'
        },
        'force': 1,
        'flags': 1,
        'from': 0,
        'to': 0
    })
    r = requests.get(
        settings.WIALON_BASE_URL + (
                '?svc=core/search_items&params=%s&sid=%s' % (request_params, sess_id)
        )
    )
    res = r.json()

    error = 'Не найден ID группового объекта.'
    if user:
        error += ' Проверьте правильность имени группового объекта в настройках интеграции ' \
                 'у пользователя "%s".' % user
    process_error(res, error)

    if 'items' not in res or len(res['items']) == 0:
        raise WialonException(error)

    return res['items'][0]['id']


def get_messages(item_id, time_from, time_to, user=None, sess_id=None):
    """Получение сообщений"""
    assert user or sess_id

    if sess_id is None:
        sess_id = get_wialon_session_key(user)

    requests.get(
        settings.WIALON_BASE_URL + (
                '?svc=messages/unload&params={}&sid=%s' % sess_id
        )
    )

    request_params = json.dumps({
        'itemId': item_id,
        'timeFrom': time_from,
        'timeTo': time_to,
        'flags': 0,
        'flagsMask': 65280,
        'loadCount': 4294967295
    })
    r = requests.get(
        settings.WIALON_BASE_URL + (
                '?svc=messages/load_interval&params=%s&sid=%s' % (request_params, sess_id)
        )
    )
    res = r.json()
    process_error(res, 'Не удалось извлечь список сообщений из Wialon. ID объекта: %s.' % item_id)

    return res


def get_points(user=None, sess_id=None):
    """Получает список геозон (точек)"""
    assert user or sess_id

    if sess_id is None:
        sess_id = get_wialon_session_key(user)

    cache_key = 'points:%s' % sess_id
    points_list = cache.get(cache_key)

    if points_list:
        return json.loads(points_list)

    request_params = json.dumps({
        'spec': {
            'itemsType': 'avl_resource',
            'propName': 'zones_library',
            'propValueMask': '*',
            'sortType': 'zones_library',
            'propType': 'propitemname'
        },
        'force': 1,
        'flags': 1 + 4096,
        'from': 0,
        'to': 0
    })
    r = requests.get(
        settings.WIALON_BASE_URL + (
            '?svc=core/search_items&params=%s&sid=%s' % (request_params, sess_id)
        )
    )
    res = r.json()

    process_error(res, 'Не удалось извлечь из Wialon список геозон.')

    points = []
    for item in res['items']:
        if item and item.get('zl'):
            points.extend([{
                'id': '%s-%s' % (item['id'], x['id']),
                'name': x['n'].strip()
            } for x in item['zl'].values()])

    if DEFAULT_CACHE_TIMEOUT:
        cache.set(cache_key, json.dumps(points), DEFAULT_CACHE_TIMEOUT)

    return points


def get_resources(user=None, sess_id=None):
    """Получает список ресурсов (организаций в рамках Виалона)"""
    assert user or sess_id

    if sess_id is None:
        sess_id = get_wialon_session_key(user)

    cache_key = 'resources:%s' % sess_id
    resources_list = cache.get(cache_key)

    if resources_list:
        return json.loads(resources_list)

    request_params = json.dumps({
        'spec': {
            'itemsType': 'avl_resource',
            'propName': 'sys_name',
            'propValueMask': '*',
            'sortType': 'sys_name',
            'propType': 'property'
        },
        'force': 1,
        'flags': 1,
        'from': 0,
        'to': 0
    })

    r = requests.get(
        settings.WIALON_BASE_URL + (
                '?svc=core/search_items&params=%s&sid=%s' % (request_params, sess_id)
        )
    )
    res = r.json()

    process_error(res, 'Не удалось извлечь из Wialon список ресурсов.')

    resources = []
    for item in res['items']:
        resources.append({
            'id': item['id'],
            'name': item['nm']
        })

    if DEFAULT_CACHE_TIMEOUT:
        cache.set(cache_key, json.dumps(resources), DEFAULT_CACHE_TIMEOUT)

    return resources


def get_resource_id(name, user=None, sess_id=None):
    """Получает ID ресурса пользователя"""
    assert user or sess_id

    if sess_id is None:
        sess_id = get_wialon_session_key(user)

    request_params = json.dumps({
        'spec': {
            'itemsType': 'avl_resource',
            'propName': 'sys_name',
            'propValueMask': name,
            'sortType': 'sys_name',
            'propType': 'property'
        },
        'force': 1,
        'flags': 1,
        'from': 0,
        'to': 0
    })
    r = requests.get(
        settings.WIALON_BASE_URL + (
                '?svc=core/search_items&params=%s&sid=%s' % (request_params, sess_id)
        )
    )
    res = r.json()

    error = 'Не найден ID ресурса.'
    if user:
        error += ' Проверьте правильность имени ресурса пользователя в настройках интеграции ' \
                 'у пользователя "%s".' % user
    process_error(res, error)

    if 'items' not in res or len(res['items']) == 0:
        raise WialonException(error)

    return res['items'][0]['id']


def get_report_template_id(name, user=None, sess_id=None):
    """Получает групповой объект"""
    assert user or sess_id

    if sess_id is None:
        sess_id = get_wialon_session_key(user)

    request_params = json.dumps({
        'spec': {
            'itemsType': 'avl_resource',
            'propName': 'reporttemplates',
            'propValueMask': name,
            'sortType': 'reporttemplates',
            'propType': 'propitemname'
        },
        'force': 1,
        'flags': 1 + 8192,
        'from': 0,
        'to': 0
    })
    r = requests.get(
        settings.WIALON_BASE_URL + (
                '?svc=core/search_items&params=%s&sid=%s' % (request_params, sess_id)
        )
    )
    res = r.json()

    error = 'Не найден ID шаблона отчета "%s"' % name
    if user:
        error += ' Проверьте правильность имени шаблона отчета в настройках интеграции ' \
                 'у пользователя "%s".' % user

    if 'error' in res and res['error'] != 1:
        try:
            send_trigger_email(
                'Шаблон отчета не найден', extra_data={
                    'Учетная запись': user,
                    'Шаблон отчета': name,
                    'Result': res
                }
            )
        except (ConnectionError, SMTPException):
            pass

    process_error(res, error)

    if 'items' not in res or len(res['items']) == 0 \
            or 'rep' not in res['items'][0] or len(res['items'][0]['rep']) == 0:
        raise WialonException(error)

    reports = list(filter(lambda x: x['n'].strip() == name, res['items'][0]['rep'].values()))
    if reports:
        return reports[0]['id']

    return None


def get_routes(user=None, sess_id=None, with_points=False):
    """Получает список маршрутов"""
    assert user or sess_id

    if sess_id is None:
        sess_id = get_wialon_session_key(user)

    cache_key = 'routes:%s:%s' % (sess_id, '1' if with_points else '0')
    routes_list = cache.get(cache_key)

    if routes_list:
        return json.loads(routes_list)

    points_dict_by_name = {}
    if with_points:
        points_dict_by_name = {x['name']: x for x in get_points(user=user, sess_id=sess_id)}

    request_params = json.dumps({
        'spec': {
            'itemsType': 'avl_route',
            'propName': 'sys_name',
            'propValueMask': '*',
            'sortType': 'sys_name',
            'propType': 'property'
        },
        'force': 1,
        'flags': 1 if not with_points else 1 + 512,
        'from': 0,
        'to': 0
    })
    r = requests.get(
        settings.WIALON_BASE_URL + (
                '?svc=core/search_items&params=%s&sid=%s' % (request_params, sess_id)
        )
    )
    res = r.json()

    process_error(res, 'Не удалось извлечь из Wialon список маршрутов.')

    routes = []
    for r in res['items']:
        route = {
            'id': r['id'],
            'name': r['nm'].strip()
        }
        if with_points:
            point_names = [x['n'] for x in r.get('rpts', [])]
            route['points'] = [
                points_dict_by_name[n]
                for n in point_names
                if n in points_dict_by_name
            ]

        routes.append(route)

    if DEFAULT_CACHE_TIMEOUT:
        cache.set(cache_key, json.dumps(routes), DEFAULT_CACHE_TIMEOUT)

    return routes


def get_units(user=None, sess_id=None, extra_fields=False):
    """Получает список элементов"""
    assert user or sess_id

    if sess_id is None:
        sess_id = get_wialon_session_key(user)

    cache_key = 'units:%s' % sess_id
    units_list = cache.get(cache_key)

    if units_list:
        return json.loads(units_list)

    request_params = json.dumps({
        'spec': {
            'itemsType': 'avl_unit',
            'propName': 'sys_name',
            'propValueMask': '*',
            'sortType': 'sys_name',
            'propType': 'property'
        },
        'force': 1,
        'flags': 1 + 8388608 + (8 if extra_fields else 0),
        'from': 0,
        'to': 0
    })
    r = requests.get(
        settings.WIALON_BASE_URL + (
                '?svc=core/search_items&params=%s&sid=%s' % (request_params, sess_id)
        )
    )
    res = r.json()
    process_error(res, 'Не удалось извлечь из Wialon список объектов (ТС).')

    units = []
    for item in res['items']:
        number, vin, vehicle_type = '', '', ''

        if 'pflds' in item:

            for f in item['pflds'].values():
                if f['n'] == 'vin':
                    vin = f['v']

                elif f['n'] == 'vehicle_type':
                    vehicle_type = f.get('v', '').strip()

                elif f['n'] == 'registration_plate':
                    number = f['v']

                if number and vin and vehicle_type:
                    break

        data = {
            'id': item['id'],
            'name': item['nm'].strip(),
            'number': number,
            'vehicle_type': vehicle_type,
            'vin': vin
        }

        if extra_fields:
            data['fields'] = list(item.get('flds', {}).values())

        units.append(data)

    if DEFAULT_CACHE_TIMEOUT:
        cache.set(cache_key, json.dumps(units), DEFAULT_CACHE_TIMEOUT)

    return units


def get_unit_settings(item_id, user=None, sess_id=None, get_sensors=True, get_features=False):
    """Получение данных о машине (объекте)"""
    assert user or sess_id

    if sess_id is None:
        sess_id = get_wialon_session_key(user)

    flags = 1
    if get_sensors:
        flags += 4096

    if get_features:
        flags += 8388608

    request_params = json.dumps({
        'id': item_id,
        'flags': flags
    })
    r = requests.get(
        settings.WIALON_BASE_URL + (
                '?svc=core/search_item&params=%s&sid=%s' % (request_params, sess_id)
        )
    )
    return r.json()['item']
