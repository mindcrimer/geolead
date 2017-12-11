# -*- coding: utf-8 -*-
from collections import OrderedDict

from django.utils.translation import ugettext_lazy as _

from snippets.models import BaseEnumerate


class JobExecutionStatusEnum(BaseEnumerate):
    NOT_AVAILABLE = 'not_available'
    NOT_FINISHED = 'not_finished'
    FINISHED = 'finished'

    values = OrderedDict((
        (NOT_AVAILABLE, _('Не исследовано')),
        (NOT_FINISHED, _('Не завершено')),
        (FINISHED, _('Завершено'))
    ))

    default = NOT_AVAILABLE
