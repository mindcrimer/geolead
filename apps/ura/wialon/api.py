# -*- coding: utf-8 -*-
import json

import requests
from django.conf import settings

from ura.wialon.auth import authenticate_at_wialon


def get_drivers_list(request, sess_id=None):
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
