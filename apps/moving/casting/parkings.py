from moving.casting import BaseCastingObject
from reports.utils import local_to_utc_time, parse_wialon_report_datetime, parse_address, \
    parse_coords


class ParkingsRow(BaseCastingObject):
    def __init__(self, dt_from, dt_to, place, *args, **kwargs):
        tz = kwargs.pop('tz')
        self.dt_from = local_to_utc_time(parse_wialon_report_datetime(dt_from), tz)
        self.dt_to = local_to_utc_time(parse_wialon_report_datetime(dt_to), tz)
        self.address = parse_address(place)
        self.coords = parse_coords(place)

    def __repr__(self):
        return '%s - %s (%s)' % (self.dt_from, self.dt_to, self.address)


def parkings_renderer(rows, **kwargs):
    return [
        ParkingsRow(*row[1:], **kwargs) for row in rows
        if '---' not in '%s|%s' % (row[1], row[2])
    ]
