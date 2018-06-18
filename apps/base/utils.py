# -*- coding: utf-8 -*-
from math import sin, cos, sqrt, atan2, radians


def parse_float(data, default=''):
    if '-' in data or not data:
        return default

    return float(data.split(' ')[0]) if data else default


def get_distance(lon1, lat1, lon2, lat2):

    # approximate radius of earth in km
    r = 6371.0

    lat1 = radians(lat1)
    lon1 = radians(lon1)
    lat2 = radians(lat2)
    lon2 = radians(lon2)

    dlon = lon2 - lon1
    dlat = lat2 - lat1

    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return r * c


def get_point_type(geozone_name):
    name = geozone_name.lower()
    point_type = 0

    if 'база' in name:
        point_type = 1

    if 'разгрузка' in name:
        point_type = 2

    if 'заправка' in name or 'азс' in name:
        point_type = 3

    if 'маршрут' in name:
        point_type = 4

    if 'погрузка' in name:
        point_type = 6

    if 'весы' in name:
        point_type = 7

    return point_type
