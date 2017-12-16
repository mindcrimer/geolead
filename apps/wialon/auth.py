# -*- coding: utf-8 -*-
import json
import urllib.request

from django.conf import settings
from django.core.cache import cache

import requests

from base.exceptions import APIProcessError


SESSION_TIMEOUT = 60 * 5


def authenticate_at_wialon(user):
    """Выполняет вход в Wialon через phantomjs и возвращает токен"""
    token = None
    return token


def login_wialon_via_token(user, token, attempt=0):
    params = urllib.request.quote(json.dumps({'token': token if token else ''}))
    r = requests.get(
        settings.WIALON_BASE_URL + ('?svc=token/login&params=%s' % params)
    )
    res = r.json()

    try:
        sess_id = res['eid']
    except (KeyError, IndexError):
        # неудачный вход. Сбиваем токен и пробуем получить новый токен, после чего повторяем вход
        user.wialon_token = None
        token = get_user_wialon_token(user)
        if token and attempt < 3:
            return login_wialon_via_token(user, token, attempt=attempt + 1)

        raise APIProcessError(
            'Невозможно открыть сессию в Wialon. Возможно, пароль пользователя недействителен.',
            code='password_invalid'
        )

    return sess_id


def get_user_wialon_token(user):
    token = user.wialon_token

    if not token:
        token = authenticate_at_wialon(user)

        if token and token != user.wialon_token:
            user.wialon_token = token
            user.save()

    return token


def get_wialon_session_key(user):
    """Возвращает идентификатор сессии пользователя Wialon"""
    cache_key = 'sessid:%s' % user.id
    sess_id = cache.get(cache_key)

    if not sess_id:
        token = get_user_wialon_token(user)
        sess_id = login_wialon_via_token(user, token)

        if sess_id:
            cache.set(cache_key, sess_id, SESSION_TIMEOUT)

    return sess_id
