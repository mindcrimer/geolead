# -*- coding: utf-8 -*-
from snippets.models import BaseEnumerate


class RedirectCodesEnum(BaseEnumerate):
    """Location redirect codes"""
    C301 = 301
    C302 = 302
    C303 = 303
    C304 = 304
    C305 = 305
    C306 = 306
    C307 = 307
    C410 = 410

    values = {
        C301: '301',
        C302: '302',
        C303: '303',
        C304: '304',
        C305: '305',
        C306: '306',
        C307: '307',
        C410: '410',
    }
