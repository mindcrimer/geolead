# -*- coding: utf-8 -*-
from copy import deepcopy

import six

from base.utils import parse_float
from reports.utils import utc_to_local_time, parse_wialon_report_datetime
from wialon import WIALON_POINT_IGNORE_TIMEOUT
from wialon.api import get_resources, get_intersected_geozones


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
        self.sess_id = None
        self.normalized_rides = []
        self.resources_cache = None
        self.route_point_names = None
        self.all_points = None
        self.all_points_names = None
        self.route = None
        self.previous_point_name = None

    @staticmethod
    def get_point_name(row_data, col_index):
        return (
            row_data[col_index]['t']
            if isinstance(row_data[col_index], dict)
            else row_data[col_index]
        ).strip()

    @staticmethod
    def get_point_coords(row_data, col_index):
        if len(row_data) > col_index and isinstance(row_data[col_index], dict):
            return {
                'lon': row_data[col_index]['x'],
                'lat': row_data[col_index]['y']
            }

        return None

    def normalize_rides(self, report_data, date_end):
        current_row, prev_row = None, None
        rides_size = len(report_data['unit_trips'])

        for i, row in enumerate(report_data['unit_trips']):
            row_data = row['c']

            time_in = row_data[self.RIDES_DATE_FROM_COL]['t'] \
                if isinstance(row_data[self.RIDES_DATE_FROM_COL], dict) \
                else row_data[self.RIDES_DATE_FROM_COL]

            time_in = utc_to_local_time(
                parse_wialon_report_datetime(time_in),
                self.request.user.ura_tz
            )

            if isinstance(row_data[self.RIDES_DATE_TO_COL], six.string_types)\
                    and row_data[self.RIDES_DATE_TO_COL].lower() == 'unknown':
                time_out = date_end

            else:
                time_out = row_data[self.RIDES_DATE_TO_COL]['t'] \
                    if isinstance(row_data[self.RIDES_DATE_TO_COL], dict) \
                    else row_data[self.RIDES_DATE_TO_COL]

                time_out = utc_to_local_time(
                    parse_wialon_report_datetime(time_out),
                    self.request.user.ura_tz
                )

            current_row = {
                'point': self.get_point_name(row_data, self.RIDES_GEOZONE_TO_COL),
                'coords': self.get_point_coords(row_data, self.RIDES_GEOZONE_TO_COL),
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
                current_row['coords'] = self.get_point_coords(
                    row_data, self.RIDES_GEOZONE_FROM_COL
                )

            # если строка не первая, тащим диапазон между строк
            if prev_row is not None:
                to_row = deepcopy(prev_row)
                to_row['point'] = self.get_point_name(row_data, self.RIDES_GEOZONE_FROM_COL)
                to_row['coords'] = self.get_point_coords(
                    row_data, self.RIDES_GEOZONE_FROM_COL
                )
                to_row['time_in'] = to_row['time_out']
                to_row['time_out'] = current_row['time_in']

                to_row['fuel_start'] = to_row['fuel_end']
                to_row['fuel_end'] = current_row['fuel_start']

                to_row['distance'] = current_row['odometer_from'] - to_row['odometer_to']

                # TODO: починить расчет пробега по координатам
                # if to_row['distance'] <= 0.0 and to_row['coords'] and current_row['coords']:
                #     to_row['distance'] = get_distance(
                #         to_row['coords']['lon'],
                #         to_row['coords']['lat'],
                #         current_row['coords']['lon'],
                #         current_row['coords']['lat']
                #     )

                to_row['odometer_from'] = to_row['odometer_to']
                to_row['odometer_to'] = current_row['odometer_from']

                self.append_to_normilized_rides(to_row)

            # в первой строке тащим точку слева, с начальными показателями на выходе
            else:
                current_row['point'] = self.get_point_name(row_data, self.RIDES_GEOZONE_TO_COL)
                current_row['coords'] = self.get_point_coords(
                    row_data, self.RIDES_GEOZONE_TO_COL
                )

                self.append_to_normilized_rides(dict(
                    point=self.get_point_name(row_data, self.RIDES_GEOZONE_FROM_COL),
                    coords=self.get_point_coords(row_data, self.RIDES_GEOZONE_FROM_COL),
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
            prev_row['coords'] = self.get_point_coords(row_data, self.RIDES_GEOZONE_TO_COL)

            # в последней записи, если она завершена, тащим точку справа
            if rides_size - i == 1 and time_out < date_end:
                self.append_to_normilized_rides(dict(
                    point=self.get_point_name(row_data, self.RIDES_GEOZONE_TO_COL),
                    coords=self.get_point_coords(row_data, self.RIDES_GEOZONE_TO_COL),
                    time_in=time_out,
                    time_out=date_end,
                    distance=0,
                    fuel_start=current_row['fuel_end'],
                    fuel_end=current_row['fuel_end'],
                    odometer_from=current_row['odometer_to'],
                    odometer_to=current_row['odometer_to']
                ))

    def append_to_normilized_rides(self, candidate_point):
        if self.normalized_rides:
            prev_point = self.normalized_rides[-1]
            delta = (candidate_point['time_out'] - candidate_point['time_in']).seconds
            # если предыдущая точка равна текущей или общий период был менее допущенного времени
            if prev_point['point'] == candidate_point['point']\
                    or (
                            self.get_normalized_point_name(candidate_point) == 'SPACE'
                            and delta < WIALON_POINT_IGNORE_TIMEOUT
                    ):
                prev_point.update(
                    time_out=candidate_point['time_out'],
                    distance=prev_point['distance'] + candidate_point['distance'],
                    fuel_end=candidate_point['fuel_end'],
                    odometer_to=candidate_point['odometer_to']
                )
                return
        self.normalized_rides.append(candidate_point)

    def get_normalized_point_name(self, row):
        point_name = row['point']

        # если маршрут или название точки вообще неизвестны, пишем SPACE
        if not self.route or point_name not in self.all_points_names:
            point_name = 'SPACE'

        # если же точка известна, но не входит в маршрут, то
        # скорее всего она пересекается с другой геозоной из маршрута
        elif point_name not in self.route_point_names:
            point_name = 'SPACE'

            if row['coords']:
                if self.resources_cache is None:
                    self.resources_cache = {
                        x['id']: [] for x in get_resources(sess_id=self.sess_id)
                    }

                intersected_geozones = get_intersected_geozones(
                    row['coords']['lon'],
                    row['coords']['lat'],
                    sess_id=self.sess_id,
                    zones=self.resources_cache
                )

                intersected_geozones_ids = set()
                [
                    intersected_geozones_ids.update([
                        '%s-%s' % (resource_id, g) for g in geozones
                    ]) for resource_id, geozones in intersected_geozones.items()
                ]
                intersected_geozones_names = list(filter(
                    lambda p: p in self.route_point_names, [
                        self.all_points[x]['name'] for x in intersected_geozones_ids
                        if x in self.all_points
                    ]
                ))

                if intersected_geozones_names:
                    # если пересекаемых точек, известных маршруту более 1, то пробуем
                    # удалить из списка предыдущую точку
                    if len(intersected_geozones_names) > 1 and self.previous_point_name:
                        intersected_geozones_names = filter(
                            lambda p: p != self.previous_point_name,
                            intersected_geozones_names
                        )
                    point_name = intersected_geozones_names[0]

        return point_name
