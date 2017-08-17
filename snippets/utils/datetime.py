# -*- coding: utf-8 -*-
from django.utils.timezone import utc

import datetime


def utcnow():
    return datetime.datetime.utcnow().replace(tzinfo=utc)
