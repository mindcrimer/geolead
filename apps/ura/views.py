# -*- coding: utf-8 -*-
from django.template.loader import render_to_string
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from lxml import etree
from lxml.etree import ParseError
from six import BytesIO

from snippets.http.response import XMLResponse
from snippets.utils.datetime import utcnow
from ura import models
from ura.utils import parse_datetime


class URAJobsView(View):
    model_mapping = {
        'name': ('jobName', str),
        'unit_id':  ('idUnit', int),
        'route_id': ('idRoute', int),
        'driver_id': ('idDriver', str),
        'driver_fio': ('driverFio', str),
        'date_begin': ('dateBegin', parse_datetime),
        'date_end': ('dateEnd', parse_datetime),
        'return_time': ('returnTime', parse_datetime),
        'leave_time': ('leaveTime', parse_datetime)
    }
    model = models.UraJob

    @csrf_exempt
    def dispatch(self, request, *args, **kwargs):
        return super(URAJobsView, self).dispatch(request, *args, **kwargs)
    
    def post(self, request, *args, **kwargs):
        jobs = []

        try:
            tree = etree.parse(BytesIO(request.body))
            jobs_els = tree.xpath('/setJobs/job')

            if jobs_els:

                for j in jobs_els:
                    job = self.model()

                    for k, v in self.model_mapping.items():
                        setattr(job, k, v[1](j.get(v[0])))

                    job.save()
                    jobs.append(job)

        except ParseError:
            pass

        result = {
            'now': utcnow(),
            'acceptedJobs': jobs
        }
        return XMLResponse(render_to_string(
            'api/ackjobs.xml', result, request=request, using='jinja2')
        )
