from collections import OrderedDict

from django.utils.translation import ugettext_lazy as _

from snippets.models import BaseEnumerate


class JobLogResolution(BaseEnumerate):
    NOT_EXAMINED = None
    APPROVED = 100
    CANCELLED = -100

    values = OrderedDict((
        (NOT_EXAMINED, _('Не рассмотрено')),
        (APPROVED, _('Подтверждено')),
        (CANCELLED, _('Отклонено'))
    ))

    default = NOT_EXAMINED
