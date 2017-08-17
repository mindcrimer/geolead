# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

from snippets.seo.models import Redirect

CACHE_TIMEOUT = timedelta(0, 600)


class LocationRouter(object):
    def __init__(self):
        self.last_modified = None
        self.routes = {}

    def _index(self):
        routes = Redirect.objects.published()
        self.routes = dict([(x.old_path, x) for x in routes])
        self.last_modified = datetime.now()

    def index(self):
        return self._index()

    def get_path(self, path):
        if self.last_modified is None or datetime.now() - self.last_modified > CACHE_TIMEOUT:
            self._index()
        return self.routes.get(path, None)


router = LocationRouter()
