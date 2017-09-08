from django.utils.timezone import get_current_timezone
from datetime import datetime


def parse_datetime(str_date):
    tz = get_current_timezone()
    return tz.localize(datetime.strptime(str_date, '%d.%m.%Y %H:%M:%S'))
