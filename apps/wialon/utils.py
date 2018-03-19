# -*- coding: utf-8 -*-
import datetime


def get_wialon_tz_integer(timezone):
    now = datetime.datetime.now()
    offset = int(timezone.utcoffset(now).total_seconds())
    return offset & 0xf000ffff | 0x08000000
