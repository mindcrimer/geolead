# -*- coding: utf-8 -*-
import json

from django.conf import settings
from django.core.cache import cache

import requests

from ura.wialon import WIALON_ENTIRE_ERROR, DEFAULT_CACHE_TIMEOUT
from ura.wialon.auth import authenticate_at_wialon
from ura.wialon.exceptions import WialonException


def get_drivers_list(user=None, sess_id=None):
    """Получает список водителей"""
    assert user or sess_id

    if sess_id is None:
        sess_id = authenticate_at_wialon(user.wialon_token)

    cache_key = 'drivers:%s' % sess_id
    drivers_list = cache.get(cache_key)

    if not drivers_list:
        request_params = json.dumps({
            'spec': {
                'itemsType': 'avl_resource',
                'propName': 'drivers',
                'propValueMask': '*',
                'sortType': 'drivers',
                'propType': 'propitemname'
            },
            'force': 1,
            'flags': 256,
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
                drivers.extend([{'id': x['id'], 'name': x['n']} for x in item['drvrs'].values()])

        cache.set(cache_key, json.dumps(drivers), DEFAULT_CACHE_TIMEOUT)
    else:
        drivers = json.loads(drivers_list)

    return drivers


def get_points_list(user=None, sess_id=None):
    """Получает список геозон (точек)"""
    assert user or sess_id

    if sess_id is None:
        sess_id = authenticate_at_wialon(user.wialon_token)

    cache_key = 'points:%s' % sess_id
    points_list = cache.get(cache_key)

    if not points_list:
        request_params = json.dumps({
            'spec': {
                'itemsType': 'avl_resource',
                'propName': 'zones_library',
                'propValueMask': '*',
                'sortType': 'zones_library',
                'propType': 'propitemname'
            },
            'force': 1,
            'flags': 4096,
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
            if item and item['zl']:
                points.extend([{
                    'id': int('%s%s' % (x['id'], x['ct'])), 'name': x['n'].strip()
                } for x in item['zl'].values()])

        cache.set(cache_key, json.dumps(points), DEFAULT_CACHE_TIMEOUT)
    else:
        points = json.loads(points_list)

    return points


def get_routes_list(user=None, sess_id=None, get_points=False):
    """Получает список маршрутов"""
    assert user or sess_id

    if sess_id is None:
        sess_id = authenticate_at_wialon(user.wialon_token)

    cache_key = 'routes:%s' % sess_id
    routes_list = cache.get(cache_key)

    if not routes_list:
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
                route['points'] = [x['n'].strip() for x in r.get('rpts', [])]

            routes.append(route)

        cache.set(cache_key, json.dumps(routes), DEFAULT_CACHE_TIMEOUT)
    else:
        routes = json.loads(routes_list)

    return routes


def get_units_list(user=None, sess_id=None, extra_fields=False):
    """Получает список элементов"""
    assert user or sess_id

    if sess_id is None:
        sess_id = authenticate_at_wialon(user.wialon_token)

    cache_key = 'units:%s' % sess_id
    units_list = cache.get(cache_key)

    if units_list:
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

        cache.set(cache_key, json.dumps(units), DEFAULT_CACHE_TIMEOUT)
    else:
        units = json.loads(units_list)

    return units
