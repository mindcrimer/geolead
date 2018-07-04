import json

from django.conf import settings
from django.core.cache import cache

import requests
from snippets.utils.email import send_trigger_email

from wialon import DEFAULT_CACHE_TIMEOUT
from wialon.exceptions import WialonException
from wialon.utils import process_error, load_requests_json


def get_drivers(sess_id):
    """Получает список водителей"""

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
    res = load_requests_json(r)

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


def get_group_object_id(name, user, sess_id):
    """Получает ID группового объекта"""
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
    res = load_requests_json(r)

    error = 'Не найден ID группового объекта. ' \
            'Проверьте правильность имени группового объекта в настройках интеграции ' \
            'у пользователя "%s".' % user
    process_error(res, error)

    if 'items' not in res or len(res['items']) == 0:
        raise WialonException(error)

    return res['items'][0]['id']


def get_messages(item_id, time_from, time_to, sess_id):
    """Получение сообщений"""
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
    res = load_requests_json(r)
    process_error(res, 'Не удалось извлечь список сообщений из Wialon. ID объекта: %s.' % item_id)

    return res


def get_points(sess_id):
    """Получает список геозон (точек)"""
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
    res = load_requests_json(r)
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


def get_resources(sess_id):
    """Получает список ресурсов (организаций в рамках Виалона)"""
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
    res = load_requests_json(r)
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


def get_resource_id(name, user, sess_id):
    """Получает ID ресурса пользователя"""
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
    res = load_requests_json(r)
    error = 'Не найден ID ресурса. ' \
            'Проверьте правильность имени ресурса пользователя в настройках интеграции ' \
            'у пользователя "%s".' % user
    process_error(res, error)

    if 'items' not in res or len(res['items']) == 0:
        raise WialonException(error)

    return res['items'][0]['id']


def get_report_template_id(name, user, sess_id):
    """Получает групповой объект"""
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
    res = load_requests_json(r)
    error = 'Не найден ID шаблона отчета "%s". ' \
            'Проверьте правильность имени шаблона отчета в настройках интеграции ' \
            'у пользователя "%s".' % (name, user)

    if 'error' in res and res['error'] != 1:
        send_trigger_email(
            'Шаблон отчета не найден', extra_data={
                'Учетная запись': user,
                'Шаблон отчета': name,
                'Result': res
            }
        )

    process_error(res, error)

    if 'items' not in res or len(res['items']) == 0 \
            or 'rep' not in res['items'][0] or len(res['items'][0]['rep']) == 0:
        raise WialonException(error)

    reports = list(filter(lambda x: x['n'].strip() == name, res['items'][0]['rep'].values()))
    if reports:
        return reports[0]['id']

    return None


def get_routes(sess_id, with_points=False):
    """Получает список маршрутов"""
    cache_key = 'routes:%s:%s' % (sess_id, '1' if with_points else '0')
    routes_list = cache.get(cache_key)

    if routes_list:
        return json.loads(routes_list)

    points_dict_by_name = {}
    if with_points:
        points_dict_by_name = {x['name']: x for x in get_points(sess_id)}

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
    res = load_requests_json(r)
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


def get_units(sess_id, extra_fields=False):
    """Получает список элементов"""
    cache_key = 'units:%s' % sess_id
    units_list = cache.get(cache_key)

    if units_list:
        return json.loads(units_list)

    flags = 1 + 8388608
    if extra_fields:
        flags += 8

    request_params = json.dumps({
        'spec': {
            'itemsType': 'avl_unit',
            'propName': 'sys_name',
            'propValueMask': '*',
            'sortType': 'sys_name',
            'propType': 'property'
        },
        'force': 1,
        'flags': flags,
        'from': 0,
        'to': 0
    })
    r = requests.get(
        settings.WIALON_BASE_URL + (
                '?svc=core/search_items&params=%s&sid=%s' % (request_params, sess_id)
        )
    )
    res = load_requests_json(r)
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


def get_drive_rank_settings(item_id, sess_id):
    """Получает настройки качества вождения"""
    request_params = json.dumps({
        'itemId': item_id,
        'sid': sess_id
    })
    r = requests.get(
        settings.WIALON_BASE_URL + (
                '?svc=unit/get_drive_rank_settings&params=%s&sid=%s' % (request_params, sess_id)
        )
    )
    res = load_requests_json(r)
    if 'error' in res:
        return {}
    result = {}

    for v in res.values():
        if isinstance(v, (list, tuple)):
            for row in v:
                result[row['name']] = row
        elif isinstance(v, dict):
            result.update(v)
    return result


def get_unit_settings(item_id, sess_id, get_sensors=True):
    """Получение данных о машине (объекте)"""
    flags = 1
    if get_sensors:
        flags += 4096

    request_params = json.dumps({
        'id': item_id,
        'flags': flags
    })
    r = requests.get(
        settings.WIALON_BASE_URL + (
                '?svc=core/search_item&params=%s&sid=%s' % (request_params, sess_id)
        )
    )
    return load_requests_json(r)['item']
