from collections import OrderedDict

from snippets.models import BaseEnumerate


class EmailDeliveryReportTypeEnum(BaseEnumerate):
    """
    Типы отчетов для рассылки
    """
    FAULTS = 'faults'
    DRIVING_STYLE = 'driving_style'

    values = OrderedDict((
        (FAULTS, 'О состоянии оборудования'),
        (DRIVING_STYLE, 'Качество вождения')
    ))
