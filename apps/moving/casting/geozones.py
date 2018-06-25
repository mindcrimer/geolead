from moving.casting import BaseCastingObject
from reports.utils import local_to_utc_time, parse_wialon_report_datetime


class GeozonesRow(BaseCastingObject):
    def __init__(self, geozone, dt_from, dt_to, *args, **kwargs):
        tz = kwargs.pop('tz')
        self.geozone = 'SPACE' if '---' in geozone else geozone.strip()
        self.dt_from = local_to_utc_time(parse_wialon_report_datetime(dt_from), tz)
        self.dt_to = local_to_utc_time(parse_wialon_report_datetime(dt_to), tz)

    def __repr__(self):
        return '%s: %s - %s' % (self.geozone, self.dt_from, self.dt_to)


def geozones_renderer(rows, **kwargs):
    return [
        GeozonesRow(*row[1:], **kwargs) for row in rows
        if '---' not in '%s|%s' % (row[2], row[3])
    ]
