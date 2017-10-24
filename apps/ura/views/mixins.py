# -*- coding: utf-8 -*-
from copy import deepcopy

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

    @staticmethod
    def get_point_name(row_data, col_index):
        return (
            row_data[col_index]['t']
            if isinstance(row_data[col_index], dict)
            else row_data[col_index]
        ).strip()

    def normalize_rides(self, report_data):
        current_row, prev_row = None, None

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

            current_row = {
                'point': self.get_point_name(row_data, self.RIDES_GEOZONE_TO_COL),
                'time_in': time_in,
                'time_out': time_out,
                'distance': parse_float(row_data[self.RIDES_DISTANCE_END_COL]),
                'fuel_start': parse_float(row_data[self.RIDES_FUEL_LEVEL_START_COL]),
                'fuel_end': parse_float(row_data[self.RIDES_FUEL_LEVEL_END_COL]),
                'odometer_from': parse_float(row_data[self.RIDES_ODOMETER_FROM_COL]),
                'odometer_to': parse_float(row_data[self.RIDES_ODOMETER_END_COL])
            }

            from_point_name = self.get_point_name(row_data, self.RIDES_GEOZONE_FROM_COL)
            if 'маршрут' in from_point_name.lower():
                current_row['point'] = from_point_name

            # если строка не первая, тащим диапазон между строк
            if prev_row is not None:
                to_row = prev_row.copy()
                to_row['point'] = self.get_point_name(row_data, self.RIDES_GEOZONE_FROM_COL)
                to_row['time_in'] = to_row['time_out']
                to_row['time_out'] = current_row['time_in']

                to_row['fuel_start'] = to_row['fuel_end']
                to_row['fuel_end'] = current_row['fuel_start']

                to_row['distance'] = current_row['odometer_from'] - to_row['odometer_to']

                to_row['odometer_from'] = to_row['odometer_to']
                to_row['odometer_to'] = current_row['odometer_from']

                self.append_to_normilized_rides(to_row)

            # в первой строке тащим точку слева, с начальными показателями на выходе
            else:
                current_row['point'] = self.get_point_name(row_data, self.RIDES_GEOZONE_TO_COL)
                self.append_to_normilized_rides(dict(
                    point=self.get_point_name(row_data, self.RIDES_GEOZONE_FROM_COL),
                    time_in=time_in,
                    time_out=time_in,
                    distance=0,
                    fuel_start=current_row['fuel_start'],
                    fuel_end=current_row['fuel_start'],
                    odometer_from=current_row['odometer_from'],
                    odometer_to=current_row['odometer_from']
                ))

            # в строке точкой маршрута является точка справа
            to_row = current_row.copy()
            self.append_to_normilized_rides(to_row)

            prev_row = deepcopy(current_row)

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
