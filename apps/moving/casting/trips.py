from moving.casting import BaseCastingObject
from reports.utils import local_to_utc_time, parse_wialon_report_datetime


class TripsRow(BaseCastingObject):
    def __init__(self, dt_from, dt_to, *args, **kwargs):
        tz = kwargs.pop('tz')
        self.dt_from = local_to_utc_time(parse_wialon_report_datetime(dt_from), tz)
        self.dt_to = local_to_utc_time(parse_wialon_report_datetime(dt_to), tz)

    def __repr__(self):
        return '%s - %s' % (self.dt_from, self.dt_to)


def trips_renderer(rows, **kwargs):
    return [
        TripsRow(*row[1:], **kwargs) for row in rows
        if '---' not in '%s|%s' % (row[1], row[2])
    ]
