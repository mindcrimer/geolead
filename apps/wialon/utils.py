import ctypes
import datetime


def get_wialon_tz_integer(timezone):
    now = datetime.datetime.now()
    offset = int(timezone.utcoffset(now).total_seconds())
    return ctypes.c_int(offset & 0xf000ffff | 0x08000000).value
