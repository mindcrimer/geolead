# -*- coding: utf-8 -*-
from ura.lib.resources import URAResource
from ura.utils import parse_datetime
from ura.views.mixins import BaseUraRidesView


class URARacesResource(BaseUraRidesView, URAResource):
    model_mapping = {
        'date_begin': ('dateBegin', parse_datetime),
        'date_end': ('dateEnd', parse_datetime),
        'job_id': ('idJob', int),
        'unit_id': ('idUnit', int),
        'route_id': ('idRoute', int)
    }

    def get_report_data_tables(self):
        pass

    def get_job(self, **kwargs):
        pass

    def post(self, request, **kwargs):
        pass
