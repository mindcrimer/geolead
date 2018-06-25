from moving.casting import BaseCastingObject


class OdometerRow(BaseCastingObject):
    def __init__(self, dt, value, *args, **kwargs):
        self.dt = dt
        self.value = value

    def __repr__(self):
        return '%s - %sкм' % (self.dt, self.value)


def odometer_renderer(rows, **kwargs):
    return [
        OdometerRow(*row[1:], **kwargs) for row in rows
        if '---' not in '%s|%s' % (row[1], row[2])
    ]
