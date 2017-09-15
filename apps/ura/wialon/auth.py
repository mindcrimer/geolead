# -*- coding: utf-8 -*-
import json
import urllib

from django.conf import settings

import requests

from ura.lib.exceptions import APIProcessError


def authenticate_at_wialon(token):
    params = urllib.request.quote(json.dumps({'token': token}))
    r = requests.get(
        settings.WIALON_BASE_URL + ('?svc=token/login&params=%s' % params)
    )
    res = r.json()
    try:
        sess_id = res['eid']
    except (KeyError, IndexError):
        raise APIProcessError(
            'Невозможно открыть сессию в Wialon. Возможно, токен недействителен или устарел.',
            code='wialon_token_invalid'
        )
    return sess_id
