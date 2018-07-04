import time

from django.utils.timezone import get_current_timezone

from reports.utils import get_wialon_report_resource_id
from ura.models import StandardPoint
from wialon.api import get_routes
from notifications.exceptions import NotificationError
from wialon.api.notifications import update_notification
from wialon.utils import get_wialon_timezone_integer


def route_coming_off_notification(job, sess_id, routes_cache=None, **kwargs):
    """1. Съезд с маршрута"""
    if not routes_cache:
        routes = get_routes(sess_id, with_points=True)
        routes_cache = {r['id']: r for r in routes}

    dt_from = int(time.mktime(job.date_begin.timetuple()))
    dt_to = int(time.mktime(job.date_end.timetuple()))

    route = routes_cache.get(int(job.route_id), {})
    route_title = route.get('name')
    geozones = route.get('points', [])
    geozones_ids = list(map(lambda x: x['id'].split('-')[1], geozones))

    if not route or not geozones:
        raise NotificationError('Маршрут неизвестен или отсутствуют геозоны. ID ПЛ=%s' % job.pk)

    data = {
        'itemId': get_wialon_report_resource_id(job.user, sess_id),
        'id': 0,
        'callMode': 'create',
        'n': 'Съезд с маршрута %s' % route_title,
        'txt': '%UNIT% съехал с маршрута. %POS_TIME% он двигался со скоростью %SPEED% около '
               '%LOCATION%',
        # время активации (UNIX формат)
        'ta': dt_from,
        # время деактивации (UNIX формат)
        'td': dt_to,
        # максимальное количество срабатываний (0 - не ограничено)
        'ma': 0,
        # таймаут срабатывания(секунд)
        'cdt': 10,
        # максимальный временной интервал между сообщениями (секунд)
        'mmtd': 60 * 60,
        # минимальная продолжительность тревожного состояния (секунд)
        'mast': 10,
        # минимальная продолжительность предыдущего состояния (секунд)
        'mpst': 10,
        # период контроля относительно текущего времени (секунд)
        'cp': 24 * 60 * 60,
        # флаги
        'fl': 0,
        # часовой пояс
        'tz': get_wialon_timezone_integer(job.user.timezone or get_current_timezone()),
        # язык пользователя (двухбуквенный код)
        'la': 'ru',
        # массив ID объектов/групп объектов
        'un': [int(job.unit_id)],
        'sch': {
            'f1': 0,
            'f2': 0,
            't1': 0,
            't2': 0,
            'm': 0,
            'y': 0,
            'w': 0
        },
        'ctrl_sch': {
            'f1': 0,
            'f2': 0,
            't1': 0,
            't2': 0,
            'm': 0,
            'y': 0,
            'w': 0
        },
        'trg': {
            't': 'geozone',
            'p': {
                'sensor_type': '',
                'sensor_name_mask': '',
                'lower_bound': 0,
                'upper_bound': 0,
                'merge': 0,
                'geozone_ids': ','.join(geozones_ids),
                'reversed': 0,
                'type': 1,
                'min_speed': 0,
                'max_speed': 0,
                'lo': 'AND'
            }
        },
        'act': [
            {
                't': 'message',
                'p': {
                    'name': 'Съезд с маршрута %s' % route_title,
                    'url': '',
                    'color': '',
                    'blink': 0
                }
            }, {
                't': 'event',
                'p': {
                    'flags': 1
                }
            }
        ]
    }

    result = update_notification(data, sess_id)
    yield result[0], result[1], data


def space_overstatements_notification(job, sess_id, routes_cache=None, **kwargs):
    """2. Перепростой вне планового маршрута"""
    if not routes_cache:
        routes = get_routes(sess_id, with_points=True)
        routes_cache = {r['id']: r for r in routes}

    dt_from = int(time.mktime(job.date_begin.timetuple()))
    dt_to = int(time.mktime(job.date_end.timetuple()))

    route = routes_cache.get(int(job.route_id), {})
    route_title = route.get('name')
    geozones = route.get('points', [])
    geozones_ids = list(map(lambda x: x['id'].split('-')[1], geozones))

    if not route or not geozones:
        raise NotificationError('Маршрут неизвестен или отсутствуют геозоны. ID ПЛ=%s' % job.pk)

    data = {
        'itemId': get_wialon_report_resource_id(job.user, sess_id),
        'id': 0,
        'callMode': 'create',
        'n': 'Перепростой вне планового маршрута %s' % route_title,
        'txt': '%UNIT% простаивал вне планового маршрута',
        # время активации (UNIX формат)
        'ta': dt_from,
        # время деактивации (UNIX формат)
        'td': dt_to,
        # максимальное количество срабатываний (0 - не ограничено)
        'ma': 0,
        # таймаут срабатывания(секунд)
        'cdt': 10,
        # максимальный временной интервал между сообщениями (секунд)
        'mmtd': 60 * 60,
        # минимальная продолжительность тревожного состояния (секунд)
        'mast': 3 * 60,
        # минимальная продолжительность предыдущего состояния (секунд)
        'mpst': 10,
        # период контроля относительно текущего времени (секунд)
        'cp': 24 * 60 * 60,
        # флаги
        'fl': 0,
        # часовой пояс
        'tz': get_wialon_timezone_integer(job.user.timezone or get_current_timezone()),
        # язык пользователя (двухбуквенный код)
        'la': 'ru',
        # массив ID объектов/групп объектов
        'un': [int(job.unit_id)],
        'sch': {
            'f1': 0,
            'f2': 0,
            't1': 0,
            't2': 0,
            'm': 0,
            'y': 0,
            'w': 0
        },
        'ctrl_sch': {
            'f1': 0,
            'f2': 0,
            't1': 0,
            't2': 0,
            'm': 0,
            'y': 0,
            'w': 0
        },
        'trg': {
            't': 'geozone',
            'p': {
                'sensor_type': 'custom',
                'sensor_name_mask': '*Скорость*',
                'lower_bound': 0,
                'upper_bound': 0,
                'prev_msg_diff': 0,
                'merge': 1,
                'geozone_ids': ','.join(geozones_ids),
                'reversed': 0,
                'type': 1,
                'min_speed': 0,
                'max_speed': 0,
                'lo': 'AND'
            }
        },
        'act': [
            {
                't': 'message',
                'p': {
                    'name': 'Перепростой вне планового маршрута %s' % route_title,
                    'url': '',
                    'color': '',
                    'blink': 0
                }
            }, {
                't': 'event',
                'p': {
                    'flags': 1
                }
            }
        ]
    }

    result = update_notification(data, sess_id)
    yield result[0], result[1], data


def route_overparking_notification(job, sess_id, routes_cache=None, job_template=None):
    """3. Перепростой на маршруте"""
    if not job_template:
        raise NotificationError('Не найден норматив шаблона задания. ID ПЛ=%s' % job.pk)

    if not routes_cache:
        routes = get_routes(sess_id, with_points=True)
        routes_cache = {r['id']: r for r in routes}

    dt_from = int(time.mktime(job.date_begin.timetuple()))
    dt_to = int(time.mktime(job.date_end.timetuple()))

    route = routes_cache.get(int(job.route_id), {})
    # ищем только маршруты
    geozones = list(filter(lambda x: 'маршрут' in x['name'].lower(), route.get('points', [])))

    if not route or not geozones:
        raise NotificationError('Маршрут неизвестен или отсутствуют геозоны. ID ПЛ=%s' % job.pk)

    for geozone in geozones:
        standard = StandardPoint.objects.filter(wialon_id=geozone['id'].strip()).first()
        if not standard or not standard.parking_time_standard:
            print(
                'Не найдена геозона или отсутствует норматив стоянок для нее. '
                'ID ПЛ=%s, ID геозоны=%s' % (
                    job.pk, geozone['id']
                )
            )
            continue

        data = {
            'itemId': get_wialon_report_resource_id(job.user, sess_id),
            'id': 0,
            'callMode': 'create',
            'n': 'Перепростой на маршруте %s' % geozone['name'],
            'txt': '%UNIT% %CURR_TIME% стоял в ' + geozone['name'] +
                   ' более нормы (' + str(standard.parking_time_standard) + ' мин.) ' +
                   'около %LOCATION%',
            # время активации (UNIX формат)
            'ta': dt_from,
            # время деактивации (UNIX формат)
            'td': dt_to,
            # максимальное количество срабатываний (0 - не ограничено)
            'ma': 0,
            # таймаут срабатывания(секунд)
            'cdt': 10,
            # максимальный временной интервал между сообщениями (секунд)
            'mmtd': 60 * 60,
            # минимальная продолжительность тревожного состояния (секунд)
            'mast': int(standard.parking_time_standard * 60),
            # минимальная продолжительность предыдущего состояния (секунд)
            'mpst': 10,
            # период контроля относительно текущего времени (секунд)
            'cp': 24 * 60 * 60,
            # флаги
            'fl': 0,
            # часовой пояс
            'tz': get_wialon_timezone_integer(job.user.timezone or get_current_timezone()),
            # язык пользователя (двухбуквенный код)
            'la': 'ru',
            # массив ID объектов/групп объектов
            'un': [int(job.unit_id)],
            'sch': {
                'f1': 0,
                'f2': 0,
                't1': 0,
                't2': 0,
                'm': 0,
                'y': 0,
                'w': 0
            },
            'ctrl_sch': {
                'f1': 0,
                'f2': 0,
                't1': 0,
                't2': 0,
                'm': 0,
                'y': 0,
                'w': 0
            },
            'trg': {
                't': 'geozone',
                'p': {
                    'sensor_type': 'custom',
                    'sensor_name_mask': '*Скорость*',
                    'lower_bound': 0,
                    'upper_bound': 0,
                    'prev_msg_diff': 0,
                    'merge': 0,
                    'geozone_ids': str(geozone['id'].split('-')[1]),
                    'reversed': 0,
                    'type': 0,
                    'min_speed': 0,
                    'max_speed': 0,
                    'lo': 'AND'
                }
            },
            'act': [
                {
                    't': 'message',
                    'p': {
                        'name': 'Перепростой на маршруте %s' % geozone['name'],
                        'url': '',
                        'color': '',
                        'blink': 0
                    }
                }, {
                    't': 'event',
                    'p': {
                        'flags': 1
                    }
                }
            ]
        }

        result = update_notification(data, sess_id)
        yield result[0], result[1], data


def load_overtime_notification(job, sess_id, routes_cache=None, job_template=None):
    """4. Превышение времени нахождения на погрузке"""
    if not job_template:
        raise NotificationError('Не найден норматив шаблона задания. ID ПЛ=%s' % job.pk)

    if not routes_cache:
        routes = get_routes(sess_id, with_points=True)
        routes_cache = {r['id']: r for r in routes}

    dt_from = int(time.mktime(job.date_begin.timetuple()))
    dt_to = int(time.mktime(job.date_end.timetuple()))

    route = routes_cache.get(int(job.route_id), {})
    # ищем только геозоны погрузки или базы
    geozones = list(
        filter(
            lambda x: 'погрузка' in x['name'].lower() or 'база' in x['name'].lower(),
            route.get('points', [])
        )
    )

    if not route or not geozones:
        raise NotificationError('Маршрут неизвестен или отсутствуют геозоны. ID ПЛ=%s' % job.pk)

    for geozone in geozones:
        standard = StandardPoint.objects.filter(wialon_id=geozone['id'].strip()).first()
        if not standard or not standard.total_time_standard:
            print(
                'Не найдена геозона погрузки/базы или отсутствует норматив нахождения для нее. '
                'ID ПЛ=%s, ID геозоны=%s' % (
                    job.pk, geozone['id']
                )
            )
            continue

        place = 'погрузке' if 'погрузка' in geozone['name'].lower() else 'базе'

        data = {
            'itemId': get_wialon_report_resource_id(job.user, sess_id),
            'id': 0,
            'callMode': 'create',
            'n': 'Превысил время нахождения на %s в %s' % (place, geozone['name']),
            'txt': '%UNIT% превысил время нахождения на ' + place + ' (' +
                   str(standard.total_time_standard) + ' мин.)' +
                   ' в ' + geozone['name'] + '. %POS_TIME% около %LOCATION%',
            # время активации (UNIX формат)
            'ta': dt_from,
            # время деактивации (UNIX формат)
            'td': dt_to,
            # максимальное количество срабатываний (0 - не ограничено)
            'ma': 0,
            # таймаут срабатывания(секунд)
            'cdt': 10,
            # максимальный временной интервал между сообщениями (секунд)
            'mmtd': 60 * 60,
            # минимальная продолжительность тревожного состояния (секунд)
            'mast': int(standard.total_time_standard * 60),
            # минимальная продолжительность предыдущего состояния (секунд)
            'mpst': 10,
            # период контроля относительно текущего времени (секунд)
            'cp': 24 * 60 * 60,
            # флаги
            'fl': 0,
            # часовой пояс
            'tz': get_wialon_timezone_integer(job.user.timezone or get_current_timezone()),
            # язык пользователя (двухбуквенный код)
            'la': 'ru',
            # массив ID объектов/групп объектов
            'un': [int(job.unit_id)],
            'sch': {
                'f1': 0,
                'f2': 0,
                't1': 0,
                't2': 0,
                'm': 0,
                'y': 0,
                'w': 0
            },
            'ctrl_sch': {
                'f1': 0,
                'f2': 0,
                't1': 0,
                't2': 0,
                'm': 0,
                'y': 0,
                'w': 0
            },
            'trg': {
                't': 'geozone',
                'p': {
                    'sensor_type': '',
                    'sensor_name_mask': '',
                    'lower_bound': 0,
                    'upper_bound': 0,
                    'merge': 0,
                    'geozone_ids': str(geozone['id'].split('-')[1]),
                    'reversed': 0,
                    'type': 0,
                    'min_speed': 0,
                    'max_speed': 0,
                    'lo': 'AND'
                }
            },
            'act': [
                {
                    't': 'message',
                    'p': {
                        'name': 'Превысил время нахождения на %s в %s' % (place, geozone['name']),
                        'url': '',
                        'color': '',
                        'blink': 0
                    }
                }, {
                    't': 'event',
                    'p': {
                        'flags': 1
                    }
                }
            ]
        }

        result = update_notification(data, sess_id)
        yield result[0], result[1], data


def unload_overtime_notification(job, sess_id, routes_cache=None, job_template=None):
    """5. Превышение времени нахождения на разгрузке"""
    if not job_template:
        raise NotificationError('Не найден норматив шаблона задания. ID ПЛ=%s' % job.pk)

    if not routes_cache:
        routes = get_routes(sess_id, with_points=True)
        routes_cache = {r['id']: r for r in routes}

    dt_from = int(time.mktime(job.date_begin.timetuple()))
    dt_to = int(time.mktime(job.date_end.timetuple()))

    route = routes_cache.get(int(job.route_id), {})
    # ищем только геозоны разгрузки
    geozones = list(
        filter(lambda x: 'разгрузка' in x['name'].lower(), route.get('points', []))
    )

    if not route or not geozones:
        raise NotificationError('Маршрут неизвестен или отсутствуют геозоны. ID ПЛ=%s' % job.pk)

    for geozone in geozones:
        standard = StandardPoint.objects.filter(wialon_id=geozone['id'].strip()).first()
        if not standard or not standard.total_time_standard:
            print(
                'Не найдена геозона разгрузки или отсутствует норматив нахождения для нее. '
                'ID ПЛ=%s, ID геозоны=%s' % (
                    job.pk, geozone['id']
                )
            )
            continue

        data = {
            'itemId': get_wialon_report_resource_id(job.user, sess_id),
            'id': 0,
            'callMode': 'create',
            'n': 'Превысил время нахождения на разгрузке в %s' % geozone['name'],
            'txt': '%UNIT% превысил время нахождения на разгрузке (' +
                   str(standard.total_time_standard) + ' мин.)' +
                   ' в ' + geozone['name'] + '. %POS_TIME% около %LOCATION%',
            # время активации (UNIX формат)
            'ta': dt_from,
            # время деактивации (UNIX формат)
            'td': dt_to,
            # максимальное количество срабатываний (0 - не ограничено)
            'ma': 0,
            # таймаут срабатывания(секунд)
            'cdt': 10,
            # максимальный временной интервал между сообщениями (секунд)
            'mmtd': 60 * 60,
            # минимальная продолжительность тревожного состояния (секунд)
            'mast': int(standard.total_time_standard * 60),
            # минимальная продолжительность предыдущего состояния (секунд)
            'mpst': 10,
            # период контроля относительно текущего времени (секунд)
            'cp': 24 * 60 * 60,
            # флаги
            'fl': 0,
            # часовой пояс
            'tz': get_wialon_timezone_integer(job.user.timezone or get_current_timezone()),
            # язык пользователя (двухбуквенный код)
            'la': 'ru',
            # массив ID объектов/групп объектов
            'un': [int(job.unit_id)],
            'sch': {
                'f1': 0,
                'f2': 0,
                't1': 0,
                't2': 0,
                'm': 0,
                'y': 0,
                'w': 0
            },
            'ctrl_sch': {
                'f1': 0,
                'f2': 0,
                't1': 0,
                't2': 0,
                'm': 0,
                'y': 0,
                'w': 0
            },
            'trg': {
                't': 'geozone',
                'p': {
                    'sensor_type': '',
                    'sensor_name_mask': '',
                    'lower_bound': 0,
                    'upper_bound': 0,
                    'merge': 0,
                    'geozone_ids': str(geozone['id'].split('-')[1]),
                    'reversed': 0,
                    'type': 0,
                    'min_speed': 0,
                    'max_speed': 0,
                    'lo': 'AND'
                }
            },
            'act': [
                {
                    't': 'message',
                    'p': {
                        'name': 'Превысил время нахождения на разгрузке в %s' % geozone['name'],
                        'url': '',
                        'color': '',
                        'blink': 0
                    }
                }, {
                    't': 'event',
                    'p': {
                        'flags': 1
                    }
                }
            ]
        }

        result = update_notification(data, sess_id)
        yield result[0], result[1], data


def space_notification(job, sess_id, routes_cache=None, job_template=None):
    """6. Нахождение объекта вне планового маршрута"""
    if not job_template or not job_template.space_overstatements_standard:
        raise NotificationError(
            'Не найден норматив перенахождения вне маршрута. ID ПЛ=%s' % job.pk
        )

    if not routes_cache:
        routes = get_routes(sess_id, with_points=True)
        routes_cache = {r['id']: r for r in routes}

    dt_from = int(time.mktime(job.date_begin.timetuple()))
    dt_to = int(time.mktime(job.date_end.timetuple()))

    route = routes_cache.get(int(job.route_id), {})
    route_title = route.get('name')
    geozones = route.get('points', [])
    geozones_ids = list(map(lambda x: x['id'].split('-')[1], geozones))

    if not route or not geozones:
        raise NotificationError('Маршрут неизвестен или отсутствуют геозоны. ID ПЛ=%s' % job.pk)

    data = {
        'itemId': get_wialon_report_resource_id(job.user, sess_id),
        'id': 0,
        'callMode': 'create',
        'n': 'Нахождение вне планового маршрута %s' % route_title,
        'txt': '%UNIT% находился вне планового маршрута ' + route_title,
        # время активации (UNIX формат)
        'ta': dt_from,
        # время деактивации (UNIX формат)
        'td': dt_to,
        # максимальное количество срабатываний (0 - не ограничено)
        'ma': 0,
        # таймаут срабатывания(секунд)
        'cdt': 10,
        # максимальный временной интервал между сообщениями (секунд)
        'mmtd': 60 * 60,
        # минимальная продолжительность тревожного состояния (секунд)
        'mast': int(job_template.space_overstatements_standard * 60.0),
        # минимальная продолжительность предыдущего состояния (секунд)
        'mpst': 10,
        # период контроля относительно текущего времени (секунд)
        'cp': 24 * 60 * 60,
        # флаги
        'fl': 0,
        # часовой пояс
        'tz': get_wialon_timezone_integer(job.user.timezone or get_current_timezone()),
        # язык пользователя (двухбуквенный код)
        'la': 'ru',
        # массив ID объектов/групп объектов
        'un': [int(job.unit_id)],
        'sch': {
            'f1': 0,
            'f2': 0,
            't1': 0,
            't2': 0,
            'm': 0,
            'y': 0,
            'w': 0
        },
        'ctrl_sch': {
            'f1': 0,
            'f2': 0,
            't1': 0,
            't2': 0,
            'm': 0,
            'y': 0,
            'w': 0
        },
        'trg': {
            't': 'geozone',
            'p': {
                'sensor_type': '',
                'sensor_name_mask': '',
                'lower_bound': 0,
                'upper_bound': 0,
                'merge': 0,
                'geozone_ids': ','.join(geozones_ids),
                'reversed': 0,
                'type': 1,
                'min_speed': 0,
                'max_speed': 0,
                'lo': 'AND'
            }
        },
        'act': [
            {
                't': 'message',
                'p': {
                    'name': 'Нахождение вне планового маршрута %s' % route_title,
                    'url': '',
                    'color': '',
                    'blink': 0
                }
            }, {
                't': 'event',
                'p': {
                    'flags': 1
                }
            }
        ]
    }

    result = update_notification(data, sess_id)
    yield result[0], result[1], data


def route_overstatement_notification(job, sess_id, routes_cache=None, job_template=None):
    """7. Превышение времени нахождения на маршруте"""
    if not job_template:
        raise NotificationError('Не найден норматив шаблона задания. ID ПЛ=%s' % job.pk)

    if not routes_cache:
        routes = get_routes(sess_id, with_points=True)
        routes_cache = {r['id']: r for r in routes}

    dt_from = int(time.mktime(job.date_begin.timetuple()))
    dt_to = int(time.mktime(job.date_end.timetuple()))

    route = routes_cache.get(int(job.route_id), {})
    # ищем только маршруты
    geozones = list(filter(lambda x: 'маршрут' in x['name'].lower(), route.get('points', [])))

    if not route or not geozones:
        raise NotificationError('Маршрут неизвестен или отсутствуют геозоны. ID ПЛ=%s' % job.pk)

    for geozone in geozones:
        standard = StandardPoint.objects.filter(wialon_id=geozone['id'].strip()).first()
        if not standard or not standard.total_time_standard:
            print(
                'Не найдена геозона или отсутствует норматив нахождения для нее. '
                'ID ПЛ=%s, ID геозоны=%s' % (
                    job.pk, geozone['id']
                )
            )
            continue

        data = {
            'itemId': get_wialon_report_resource_id(job.user, sess_id),
            'id': 0,
            'callMode': 'create',
            'n': 'Превысил время нахождения на маршруте %s' % geozone['name'],
            'txt': '%UNIT% %CURR_TIME% превысил время нахождения (' +
                   str(standard.total_time_standard) + ' мин.) на маршруте ' + geozone['name'],
            # время активации (UNIX формат)
            'ta': dt_from,
            # время деактивации (UNIX формат)
            'td': dt_to,
            # максимальное количество срабатываний (0 - не ограничено)
            'ma': 0,
            # таймаут срабатывания(секунд)
            'cdt': 10,
            # максимальный временной интервал между сообщениями (секунд)
            'mmtd': 60 * 60,
            # минимальная продолжительность тревожного состояния (секунд)
            'mast': int(standard.total_time_standard * 60),
            # минимальная продолжительность предыдущего состояния (секунд)
            'mpst': 10,
            # период контроля относительно текущего времени (секунд)
            'cp': 24 * 60 * 60,
            # флаги
            'fl': 0,
            # часовой пояс
            'tz': get_wialon_timezone_integer(job.user.timezone or get_current_timezone()),
            # язык пользователя (двухбуквенный код)
            'la': 'ru',
            # массив ID объектов/групп объектов
            'un': [int(job.unit_id)],
            'sch': {
                'f1': 0,
                'f2': 0,
                't1': 0,
                't2': 0,
                'm': 0,
                'y': 0,
                'w': 0
            },
            'ctrl_sch': {
                'f1': 0,
                'f2': 0,
                't1': 0,
                't2': 0,
                'm': 0,
                'y': 0,
                'w': 0
            },
            'trg': {
                't': 'geozone',
                'p': {
                    'sensor_type': '',
                    'sensor_name_mask': '',
                    'lower_bound': 0,
                    'upper_bound': 0,
                    'merge': 0,
                    'geozone_ids': str(geozone['id'].split('-')[1]),
                    'reversed': 0,
                    'type': 0,
                    'min_speed': 0,
                    'max_speed': 0,
                    'lo': 'AND'
                }
            },
            'act': [
                {
                    't': 'message',
                    'p': {
                        'name': 'Превысил время нахождения на маршруте %s' % geozone['name'],
                        'url': '',
                        'color': '',
                        'blink': 0
                    }
                }, {
                    't': 'event',
                    'p': {
                        'flags': 1
                    }
                }
            ]
        }

        result = update_notification(data, sess_id)
        yield result[0], result[1], data
