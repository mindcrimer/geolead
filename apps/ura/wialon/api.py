# -*- coding: utf-8 -*-
import json

import requests
from django.conf import settings

from ura.wialon.auth import authenticate_at_wialon


def get_drivers_list(request, sess_id=None):
    """Получает список водителей"""
    if sess_id is None:
        sess_id = authenticate_at_wialon(request.user.wialon_token)

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

    drivers = []
    for item in res['items']:
        if item['drvrs']:
            drivers.extend([{'id': x['id'], 'name': x['n']} for x in item['drvrs'].values()])

    return drivers


def get_routes_list(request, sess_id=None):
    """Получает список маршрутов"""
    if sess_id is None:
        sess_id = authenticate_at_wialon(request.user.wialon_token)

    request_params = json.dumps({
        'spec': {
            'itemsType': 'avl_route',
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

    routes = [{'id': r['id'], 'name': r['nm']} for r in res['items']]
    return routes


def get_units_list(request, sess_id=None):
    """Получает список элементов"""
    if sess_id is None:
        sess_id = authenticate_at_wialon(request.user.wialon_token)

    request_params = json.dumps({
        'spec': {
            'itemsType': 'avl_unit',
            'propName': 'sys_name',
            'propValueMask': '*',
            'sortType': 'sys_name',
            'propType': 'property'
        },
        'force': 1,
        'flags': 1 + 8388608,
        'from': 0,
        'to': 0
    })
    r = requests.get(
        settings.WIALON_BASE_URL + (
            '?svc=core/search_items&params=%s&sid=%s' % (request_params, sess_id)
        )
    )
    res = r.json()

    units = []
    for item in res['items']:
        number, vin = '', ''

        for f in item['pflds'].values():
            if f['n'] == 'vin':
                vin = f['v']

            elif f['n'] == 'registration_plate':
                number = f['v']

            if number and vin:
                break

        units.append({
            'id': item['id'],
            'name': item['nm'],
            'number': number,
            'vin': vin
        })

    return units
