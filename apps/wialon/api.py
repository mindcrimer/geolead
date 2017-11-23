# -*- coding: utf-8 -*-
import json

from django.conf import settings
from django.core.cache import cache

import requests

from wialon import WIALON_ENTIRE_ERROR, DEFAULT_CACHE_TIMEOUT
from wialon.exceptions import WialonException
from wialon.auth import get_wialon_session_key


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

    if 'error' in res:
        raise WialonException(WIALON_ENTIRE_ERROR)

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


def get_intersected_geozones(lon, lat, user=None, sess_id=None, zones=None):
    """Получает геозоны, пересекаемые c указанной координатой"""
    assert user or sess_id

    if sess_id is None:
        sess_id = get_wialon_session_key(user)

    if zones is None:
        zones = {x['id']: [] for x in get_resources(user, sess_id)}

    request_params = json.dumps({
        'spec': {
            'zoneId': zones,
            'lat': lat,
            'lon': lon
        }
    })
    r = requests.get(
        settings.WIALON_BASE_URL + (
            '?svc=resource/get_zones_by_point&params=%s&sid=%s' % (request_params, sess_id)
        )
    )
    res = r.json()

    return res


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

    if 'error' in res:
        raise WialonException(WIALON_ENTIRE_ERROR)

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

    if 'error' in res:
        raise WialonException(WIALON_ENTIRE_ERROR)

    points = []
    for item in res['items']:
        if item and item.get('zl'):
            points.extend([{
                'id': '%s-%s' % (item['id'], x['id']), 'name': x['n'].strip()
            } for x in item['zl'].values()])

    if DEFAULT_CACHE_TIMEOUT:
        cache.set(cache_key, json.dumps(points), DEFAULT_CACHE_TIMEOUT)

    return points


def get_report_templates(user=None, sess_id=None):
    """Получает список шаблонов отчетов"""
    assert user or sess_id

    if sess_id is None:
        sess_id = get_wialon_session_key(user)

    cache_key = 'report_templates:%s' % sess_id
    report_templates_list = cache.get(cache_key)

    if report_templates_list:
        return json.loads(report_templates_list)

    request_params = json.dumps({
        'spec': {
            'itemsType': 'avl_resource',
            'propName': 'reporttemplates',
            'propValueMask': '*',
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

    if 'error' in res:
        raise WialonException(WIALON_ENTIRE_ERROR)

    report_templates = []
    for item in res['items']:
        if item and item['rep']:
            report_templates.extend([{
                'id': '%s-%s' % (item['id'], x['id']),
                'name': x['n']
            } for x in item['rep'].values()])

    if DEFAULT_CACHE_TIMEOUT:
        cache.set(cache_key, json.dumps(report_templates), DEFAULT_CACHE_TIMEOUT)

    return report_templates


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

    if 'error' in res:
        raise WialonException(WIALON_ENTIRE_ERROR)

    resources = []
    for item in res['items']:
        resources.append({
            'id': item['id'],
            'name': item['nm']
        })

    if DEFAULT_CACHE_TIMEOUT:
        cache.set(cache_key, json.dumps(resources), DEFAULT_CACHE_TIMEOUT)

    return resources


def get_routes(user=None, sess_id=None, with_points=False):
    """Получает список маршрутов"""
    assert user or sess_id

    if sess_id is None:
        sess_id = get_wialon_session_key(user)

    cache_key = 'routes:%s' % sess_id
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
        'flags': 1 if not get_points else 1 + 512,
        'from': 0,
        'to': 0
    })
    r = requests.get(
        settings.WIALON_BASE_URL + (
            '?svc=core/search_items&params=%s&sid=%s' % (request_params, sess_id)
        )
    )
    res = r.json()

    if 'error' in res:
        raise WialonException(WIALON_ENTIRE_ERROR)

    routes = []
    for r in res['items']:
        route = {
            'id': r['id'],
            'name': r['nm'].strip()
        }
        if get_points:
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

    if 'error' in res:
        raise WialonException(WIALON_ENTIRE_ERROR)

    units = []
    for item in res['items']:
        number, vin = '', ''

        if 'pflds' in item:

            for f in item['pflds'].values():
                if f['n'] == 'vin':
                    vin = f['v']

                elif f['n'] == 'registration_plate':
                    number = f['v']

                if number and vin:
                    break

        data = {
            'id': item['id'],
            'name': item['nm'].strip(),
            'number': number,
            'vin': vin
        }

        if extra_fields:
            data['fields'] = list(item.get('flds', {}).values())

        units.append(data)

    if DEFAULT_CACHE_TIMEOUT:
        cache.set(cache_key, json.dumps(units), DEFAULT_CACHE_TIMEOUT)

    return units


def get_unit_settings(item_id, user=None, sess_id=None):
    """Получение данных о машине (объекте)"""
    assert user or sess_id

    if sess_id is None:
        sess_id = get_wialon_session_key(user)

    request_params = json.dumps({
        'id': item_id,
        'flags': 1 + 4096
    })
    r = requests.get(
        settings.WIALON_BASE_URL + (
            '?svc=core/search_item&params=%s&sid=%s' % (request_params, sess_id)
        )
    )
    return r.json()['item']
