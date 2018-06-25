from moving.casting.angle_sensor import angle_sensor_renderer
from moving.casting.discharges import discharges_renderer
from moving.casting.fuel_levels import fuel_level_renderer
from moving.casting.geozones import geozones_renderer
from moving.casting.last_data import last_data_renderer
from moving.casting.motohours import motohours_renderer
from moving.casting.odometer import odometer_renderer
from moving.casting.parkings import parkings_renderer
from moving.casting.refillings import refillings_renderer
from moving.casting.trips import trips_renderer


MOVING_SERVICE_MAPPING = {
    'геозоны': {
        'name': 'geozones',
        'level': 2,
        'renderer': geozones_renderer
    },
    'моточасы': {
        'name': 'motohours',
        'level': 2,
        'renderer': motohours_renderer
    },
    'заправки': {
        'name': 'refillings',
        'level': 2,
        'renderer': refillings_renderer
    },
    'сливы': {
        'name': 'discharges',
        'level': 2,
        'renderer': discharges_renderer
    },
    'поездки': {
        'name': 'trips',
        'level': 2,
        'renderer': trips_renderer
    },
    'стоянки': {
        'name': 'parkings',
        'level': 2,
        'renderer': parkings_renderer
    },
    'уровень топлива': {
        'name': 'fuel_level',
        'level': 2,
        'renderer': fuel_level_renderer
    },
    'последние данные': {
        'name': 'last_data',
        'level': 1,
        'renderer': last_data_renderer
    },
    'дун': {
        'name': 'angle_sensor',
        'level': 2,
        'renderer': angle_sensor_renderer
    },
    'пробег': {
        'name': 'odometer',
        'level': 0,
        'renderer': odometer_renderer
    }
}


class ReportTable(object):
    """Таблица отчета для каждого объекта"""
    def __init__(self, name):
        self.name = name
        # первичный слой данных
        self.source = []
        # вторичный слой (обработанный)
        self.target = []

        self.target_analyzed = False

    def append_source(self, value):
        self.source.append(value)

    def extend_source(self, values):
        self.source.extend(values)

    def length(self):
        return len(self.source)

    def __str__(self):
        return '%s (%s)' % (self.name, self.length())

    def __repr__(self):
        return self.__str__()


class ReportUnit(object):
    """Объект в отчете"""
    def __init__(self, unit):
        self.unit = unit
        for field in MOVING_SERVICE_MAPPING.values():
            setattr(self, field['name'], ReportTable(field['name']))

    def __str__(self):
        return '%s (%s)' % (
            self.unit['name'],
            sum([getattr(self, x['name']).length() for x in MOVING_SERVICE_MAPPING.values()])
        )

    def __repr__(self):
        return self.__str__()
