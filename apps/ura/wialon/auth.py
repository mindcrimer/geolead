# -*- coding: utf-8 -*-
import json
import urllib

from django.conf import settings
from django.core.cache import cache

import requests

from ura.lib.exceptions import APIProcessError


def authenticate_at_wialon(token):
    # TODO кэшировать сессию на 5 минут по токену
    cache_key = 'sessid:%s' % token
    sess_id = cache.get(cache_key)

    if not sess_id:
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
        cache.set(cache_key, sess_id, 60 * 5)

    return sess_id
