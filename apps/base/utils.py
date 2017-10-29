# -*- coding: utf-8 -*-
from math import sin, cos, sqrt, atan2, radians


def parse_float(data):
    if '-' in data or not data:
        return ''

    return float(data.split(' ')[0]) if data else ''


def get_distance(lon1, lat1, lon2, lat2):

    # approximate radius of earth in km
    r = 6373.0

    lat1 = radians(lat1)
    lon1 = radians(lon1)
    lat2 = radians(lat2)
    lon2 = radians(lon2)

    dlon = lon2 - lon1
    dlat = lat2 - lat1

    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    distance = r * c

    return distance
