from moving.casting import BaseCastingObject
from reports.utils import local_to_utc_time, parse_wialon_report_datetime, parse_address, \
    parse_coords


class LastDataRow(BaseCastingObject):
    def __init__(self, last_message, last_coords, place, *args, **kwargs):
        tz = kwargs.pop('tz')
        self.last_message = local_to_utc_time(parse_wialon_report_datetime(last_message), tz)
        self.last_coords = local_to_utc_time(parse_wialon_report_datetime(last_coords), tz)
        self.address = parse_address(place)
        self.coords = parse_coords(place)

    def __repr__(self):
        return '%s, %s (%s)' % (self.last_message, self.last_coords, self.address)


def last_data_renderer(rows, **kwargs):
    return [
        LastDataRow(*row[1:], **kwargs) for row in rows
        if '---' not in '%s|%s' % (row[1], row[2])
    ]
