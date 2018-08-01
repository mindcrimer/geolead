import time

from django.conf import settings

import redis

from snippets.utils.passwords import generate_random_string
from wialon.auth import get_user_wialon_token, login_wialon_via_token


class SessionStore(object):
    expiraton_seconds = settings.WIALON_SESSION_TIMEOUT

    def __init__(self):
        self.connection_pool = redis.BlockingConnectionPool(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB
        )
        self.cache = self.make_connection()

    def make_connection(self):
        return redis.Redis(connection_pool=self.connection_pool)

    @staticmethod
    def get_user_pattern(user):
        return 'sessid:%s:*' % user.id

    @staticmethod
    def generate_cache_key(user):
        return 'sessid:%s:%s' % (user.id, generate_random_string(8))

    @staticmethod
    def get_expiry_key(sess_id):
        return 'sessid:expiry:%s' % sess_id

    def set_session_key(self, sess_id, user, timeout=settings.WIALON_SESSION_TIMEOUT):
        self.cache.setex(self.generate_cache_key(user), sess_id, timeout)
        # удаляем кэш срока годности
        self.cache.delete(self.get_expiry_key(sess_id))

    def acquire_session_key(self, sess_id):
        # оставляем метку когда начали пользоваться
        self.cache.setex(self.get_expiry_key(sess_id), int(time.time()), self.expiraton_seconds)

    def get_new_session_key(self, user):
        token = get_user_wialon_token(user)
        sess_id = login_wialon_via_token(user, token)
        self.acquire_session_key(sess_id)
        return sess_id

    def get_session_key(self, user, invalidate=False):
        if invalidate:
            return self.get_new_session_key(user)

        keys = self.cache.keys(self.get_user_pattern(user))
        if not keys:
            return self.get_new_session_key(user)

        sess_id = None
        while keys:
            # стараемся сначала переиспользовать более ранний ключ
            key = keys.pop()
            sess_id = self.cache.get(key)
            self.cache.delete(key)
            # уже успело устареть или быть занятым:
            if sess_id is not None:
                sess_id = sess_id.decode()
                self.acquire_session_key(sess_id)
                break

        if not sess_id:
            return self.get_new_session_key(user)

        return sess_id

    def return_session_key(self, sess_id, user):
        created_at = self.cache.get(self.get_expiry_key(sess_id))
        if created_at is not None:
            # значит сессионный ключ еще актуален
            delta = int(time.time()) - int(created_at)
            # если осталось болье 1 секунды, то даем сохранить
            if delta < self.expiraton_seconds:
                self.set_session_key(sess_id, user, self.expiraton_seconds - delta)
            return True
        return False


session_store = SessionStore()


def get_wialon_session_key(user, invalidate=False):
    """Возвращает идентификатор сессии пользователя Wialon"""
    return session_store.get_session_key(user, invalidate=invalidate)


def logout_session(user, sess_id):
    """Сохраняет обратно сессионный ключ для повторного использования"""
    return session_store.return_session_key(sess_id, user)
