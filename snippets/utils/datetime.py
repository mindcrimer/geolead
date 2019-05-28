import pytz

import datetime

from django.conf import settings


def utcnow():
    now = datetime.datetime.now()
    dt = pytz.timezone(settings.TIME_ZONE).localize(now, is_dst=None)
    return dt.astimezone(pytz.utc)
