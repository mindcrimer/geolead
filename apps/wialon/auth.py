import json
import os
import subprocess
import urllib.request
from time import sleep

from django.conf import settings

import requests

from base.exceptions import APIProcessError
from snippets.utils.email import send_trigger_email
from wialon.sessions import session_store
from wialon.utils import load_requests_json


def get_session_cache_key(user):
    return 'sessid:%s' % user.id


def get_wialon_session_key(user, invalidate=False):
    """Возвращает идентификатор сессии пользователя Wialon"""
    return session_store.get_session_key(user, invalidate=invalidate)
    # cache_key = get_session_cache_key(user)
    # sess_id = cache.get(cache_key)
    #
    # if not sess_id or invalidate:
    #     token = get_user_wialon_token(user)
    #     sess_id = login_wialon_via_token(user, token)
    #
    #     if sess_id:
    #         cache.set(cache_key, sess_id, settings.WIALON_SESSION_TIMEOUT)
    #
    # return sess_id


def login_wialon_via_token(user, token, attempt=0):
    if attempt > 5:
        raise APIProcessError(
            'Невозможно открыть сессию в Wialon. Возможно, пароль пользователя недействителен. '
            'Пользователь: %s' % user,
            code='password_invalid'
        )

    params = urllib.request.quote(json.dumps({'token': token if token else ''}))
    r = requests.get(
        settings.WIALON_BASE_URL + ('?svc=token/login&params=%s' % params)
    )
    res = load_requests_json(r)

    # какие-то проблемы с лимитами
    if res.get('error', 0) == 1:
        sleep(3)
        login_wialon_via_token(user, token, attempt=attempt + 1)

    try:
        sess_id = res['eid']
    except (KeyError, IndexError):
        print('Новая попытка входа после неудачи. Пользователь: %s' % user)
        # неудачный вход. Сбиваем токен и пробуем получить новый токен, после чего повторяем вход
        user.wialon_token = None
        token = get_user_wialon_token(user)
        return login_wialon_via_token(user, token, attempt=attempt + 1)

    return sess_id


def authenticate_at_wialon(user):
    """Выполняет вход в Wialon через phantomjs и возвращает токен"""
    phantomjs_bin = os.path.join(settings.STATIC_ROOT, 'node_modules/phantomjs/bin/phantomjs')
    phantomjs_js = os.path.join(settings.STATIC_ROOT, 'vendors/login.js')
    args = [
        phantomjs_bin,
        phantomjs_js,
        user.wialon_username,
        user.wialon_password
    ]
    result = subprocess.check_output(args, universal_newlines=True)

    if not result:
        return None

    token_key = 'access_token'
    if token_key not in result:
        print(result)
        send_trigger_email(
            'Ошибка входа в Wialon', extra_data={
                'result': result,
                'user': user
            }
        )
        return None

    parts = [x.split('=') for x in result.split('?')[1].split('&')]
    parts = {x[0]: x[1] for x in parts}
    token = parts.get(token_key)

    if not token:
        print(result)
        send_trigger_email(
            'Ошибка входа в Wialon', extra_data={
                'result': result,
                'user': user
            }
        )

    return token


def get_user_wialon_token(user):
    token = user.wialon_token

    if not token:
        token = authenticate_at_wialon(user)

        if token and token != user.wialon_token:
            user.wialon_token = token
            user.save()

    return token


def logout_session(user, sess_id):
    # params = urllib.request.quote('{}')
    # r = requests.get(
    #     settings.WIALON_BASE_URL + ('?svc=core/logout&params=%s&sid=%s' % (params, sess_id))
    # )
    # res = load_requests_json(r)
    #
    # succeeded = res.get('error', 0) == 0
    # if succeeded:
    #     # удаляем из кэша
    #     cache_key = get_session_cache_key(user)
    #     cached_sess_id = cache.get(cache_key)
    #     if cached_sess_id and cached_sess_id == sess_id:
    #         cache.delete(cache_key)
    #
    # return succeeded

    # пока отключил, чтобы не убивало так необходимый кэш
    # return False
    return session_store.return_session_key(sess_id, user)
