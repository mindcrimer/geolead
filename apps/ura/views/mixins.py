# -*- coding: utf-8 -*-
from base.utils import parse_float
from reports.utils import utc_to_local_time, parse_wialon_report_datetime


class RidesMixin(object):
    normalized_rides = None

    RIDES_DATE_FROM_COL = 0
    RIDES_DATE_TO_COL = 1
    RIDES_GEOZONE_FROM_COL = 2
    RIDES_GEOZONE_TO_COL = 3
    RIDES_DISTANCE_END_COL = 4
    RIDES_FUEL_LEVEL_START_COL = 5
    RIDES_FUEL_LEVEL_END_COL = 6
    RIDES_ODOMETER_FROM_COL = 7
    RIDES_ODOMETER_END_COL = 8

    def __init__(self):
        super(RidesMixin, self).__init__()
        self.normalized_rides = []

    def normalize_rides(self, report_data):
        from_row, to_row = None, None

        for i, row in enumerate(report_data['unit_trips']):
            row_data = row['c']

            time_in = row_data[self.RIDES_DATE_FROM_COL]['t'] \
                if isinstance(row_data[self.RIDES_DATE_FROM_COL], dict) \
                else row_data[self.RIDES_DATE_FROM_COL]

            time_in = utc_to_local_time(
                parse_wialon_report_datetime(time_in),
                self.request.user.ura_tz
            )

            time_out = row_data[self.RIDES_DATE_TO_COL]['t'] \
                if isinstance(row_data[self.RIDES_DATE_TO_COL], dict) \
                else row_data[self.RIDES_DATE_TO_COL]

            time_out = utc_to_local_time(
                parse_wialon_report_datetime(time_out),
                self.request.user.ura_tz
            )

            row = {
                'time_in': time_in,
                'time_out': time_out,
                'distance': parse_float(row_data[self.RIDES_DISTANCE_END_COL]),
                'fuel_start': parse_float(row_data[self.RIDES_FUEL_LEVEL_START_COL]),
                'fuel_end': parse_float(row_data[self.RIDES_FUEL_LEVEL_END_COL]),
                'odometer_from': parse_float(row_data[self.RIDES_ODOMETER_FROM_COL]),
                'odometer_to': parse_float(row_data[self.RIDES_ODOMETER_END_COL])
            }

            from_row = row.copy()
            from_row['point'] = (
                row_data[self.RIDES_GEOZONE_FROM_COL]['t']
                if isinstance(row_data[self.RIDES_GEOZONE_FROM_COL], dict)
                else row_data[self.RIDES_GEOZONE_FROM_COL]
            ).strip()

            if to_row is not None:
                to_row = to_row.copy()
                to_row['time_in'] = to_row['time_out']
                to_row['time_out'] = from_row['time_in']

                to_row['fuel_start'] = to_row['fuel_end']
                to_row['fuel_end'] = from_row['fuel_start']

                to_row['distance'] = from_row['odometer_from'] - to_row['odometer_to']

                to_row['odometer_from'] = to_row['odometer_to']
                to_row['odometer_to'] = from_row['odometer_from']

                self.append_to_normilized_rides(to_row)

            self.append_to_normilized_rides(from_row)

            to_row = row.copy()
            to_row['point'] = (
                row_data[self.RIDES_GEOZONE_TO_COL]['t']
                if isinstance(row_data[self.RIDES_GEOZONE_TO_COL], dict)
                else row_data[self.RIDES_GEOZONE_TO_COL]
            ).strip()

    def append_to_normilized_rides(self, candidate_point):
        if self.normalized_rides:
            prev_point = self.normalized_rides[-1]
            if prev_point['point'] == candidate_point['point']:
                prev_point.update(
                    time_out=candidate_point['time_out'],
                    distance=prev_point['distance'] + candidate_point['distance'],
                    fuel_end=candidate_point['fuel_end'],
                    odometer_to=candidate_point['odometer_to']
                )
                return
        self.normalized_rides.append(candidate_point)
