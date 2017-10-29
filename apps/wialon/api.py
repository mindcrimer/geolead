# -*- coding: utf-8 -*-
import json

import requests
from django.conf import settings
from django.core.cache import cache
from wialon import WIALON_ENTIRE_ERROR, DEFAULT_CACHE_TIMEOUT
from wialon.exceptions import WialonException

from wialon.auth import authenticate_at_wialon


def get_drivers(user=None, sess_id=None):
    """Получает список водителей"""
    assert user or sess_id

    if sess_id is None:
        sess_id = authenticate_at_wialon(user.wialon_token)

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


def get_intersected_geozones(sess_id, lon, lat, zones=None):
    """Получает геозоны, пересекаемые c указанной координатой"""
    if zones is None:
        pass

    request_params = json.dumps({
        'spec': {
            'zoneId': {15947710: []},
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
        sess_id = authenticate_at_wialon(user.wialon_token)

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
        sess_id = authenticate_at_wialon(user.wialon_token)

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


def get_resources(user=None, sess_id=None):
    """Получает список ресурсов (организаций в рамках Виалона)"""
    assert user or sess_id

    if sess_id is None:
        sess_id = authenticate_at_wialon(user.wialon_token)

    cache_key = 'resources:%s' % sess_id
    resources_list = cache.get(cache_key)

    if resources_list:
        return json.loads(resources_list)

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

    resources = []
    for item in res['items']:
        if item and item['drvrs']:
            resources.extend([{
                'id': '%s-%s' % (item['id'], x['id']),
                'name': x['n']
            } for x in item['drvrs'].values()])

    if DEFAULT_CACHE_TIMEOUT:
        cache.set(cache_key, json.dumps(resources), DEFAULT_CACHE_TIMEOUT)

    return resources


def get_routes(user=None, sess_id=None, get_points=False):
    """Получает список маршрутов"""
    assert user or sess_id

    if sess_id is None:
        sess_id = authenticate_at_wialon(user.wialon_token)

    cache_key = 'routes:%s' % sess_id
    routes_list = cache.get(cache_key)

    if routes_list:
        return json.loads(routes_list)

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
            route['points'] = [{
                'id': '%s-%s' % (route['id'], x['id']), 'name': x['n'].strip()
            } for x in r.get('rpts', [])]

        routes.append(route)

    if DEFAULT_CACHE_TIMEOUT:
        cache.set(cache_key, json.dumps(routes), DEFAULT_CACHE_TIMEOUT)

    return routes


def get_units(user=None, sess_id=None, extra_fields=False):
    """Получает список элементов"""
    assert user or sess_id

    if sess_id is None:
        sess_id = authenticate_at_wialon(user.wialon_token)

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

