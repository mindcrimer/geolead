class BaseCastingObject(object):
    def __str__(self):
        return self.__repr__()


class IntersectionPeriod(BaseCastingObject):
    def __init__(self, row, dt_from, dt_to):
        self.row = row
        self.dt_from = dt_from
        self.dt_to = dt_to

    def __repr__(self):
        return '%s - %s' % (self.dt_from, self.dt_to)


class IntersectionMoment(BaseCastingObject):
    def __init__(self, row, dt, volume):
        self.row = row
        self.dt = dt
        self.volume = volume

    def __repr__(self):
        return '%s (%s)' % (self.dt, self.volume)
