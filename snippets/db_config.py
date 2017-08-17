# -*- coding: utf-8 -*-
import datetime
from collections import defaultdict

from django.conf import settings

from snippets.general.models import DbConfig
from snippets.models.enumerates import StatusEnum
from snippets.utils.datetime import utcnow

CACHE_TIMEOUT = datetime.timedelta(0, 30)


class DBVar(object):
    def __init__(self):
        self.last_modified = None
        self.vars = {}
        self.default_language_code = settings.DEFAULT_LANGUAGE

    def index(self, force=False):
        now = utcnow()
        if force \
                or self.last_modified is None \
                or now - self.last_modified > CACHE_TIMEOUT:

            self.vars = defaultdict(dict)

            values = DbConfig.objects.filter(status=StatusEnum.PUBLIC)
            for value in values.iterator():
                for lang in settings.LANGUAGE_CODES:
                    self.vars[lang][value.key] = getattr(value, 'value_' + lang)
            self.last_modified = now

    def force_index(self):
        return self.index(force=True)

    def get(self, key, lang, default_value=''):
        self.index()
        var = self.vars[lang].get(key, None)
        var = self.vars[lang].get(self.default_language_code, None) if var is None else var
        return var or default_value

    def all(self, lang):
        self.index()
        return self.vars[lang]


db_vars = DBVar()
