from moving.casting import BaseCastingObject


class Visit(BaseCastingObject):
    def __init__(self, geozone, dt_from, dt_to, geozone_full=None):
        self.geozone = geozone
        self.dt_from = dt_from
        self.dt_to = dt_to
        self.geozone_full = geozone_full or geozone

    def __repr__(self):
        return '%s: %s - %s' % (self.geozone, self.dt_from, self.dt_to)
