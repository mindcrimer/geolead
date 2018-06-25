from base.utils import parse_float
from moving.casting import BaseCastingObject
from reports.utils import local_to_utc_time, parse_wialon_report_datetime


class DischargesRow(BaseCastingObject):
    def __init__(self, dt, volume, *args, **kwargs):
        tz = kwargs.pop('tz')
        self.dt = local_to_utc_time(parse_wialon_report_datetime(dt), tz)
        self.volume = parse_float(volume)

    def __repr__(self):
        return '%s - %sл' % (self.dt, self.volume)


def discharges_renderer(rows, **kwargs):
    return [
        DischargesRow(*row[1:], **kwargs) for row in rows
        if '---' not in '%s|%s' % (row[1], row[2])
    ]
