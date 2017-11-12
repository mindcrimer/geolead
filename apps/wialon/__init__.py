# -*- coding: utf-8 -*-
from django.conf import settings


WIALON_SESSION_ERROR = 'Возможно, сессия устарела. Попробуйте заново войти в Wialon'
WIALON_ENTIRE_ERROR = 'Произвошла ошибка в источнике данных. ' \
                      'Повторите запрос через некоторое время или заново выполните вход.'

DEFAULT_CACHE_TIMEOUT = settings.WIALON_CACHE_TIMEOUT

# максимальный период схода с маршрута, который можно проигнорировать
# (и назначить предыдущей точке)
WIALON_POINT_IGNORE_TIMEOUT = 60
