# -*- coding: utf-8 -*-


def parse_float(data):
    if '-' in data or not data:
        return ''

    return float(data.split(' ')[0]) if data else ''
