# -*- coding: utf-8 -*-
from snippets.utils.datetime import utcnow
from ura import models
from ura.lib.resources import URAResource
from ura.lib.response import XMLResponse, error_response
from ura.utils import parse_xml_input_data, parse_datetime, register_job_notifications
from wialon.api import get_routes, get_units


class URASetJobsResource(URAResource):
    model_mapping = {
        'name': ('jobName', str),
        'unit_id':  ('idUnit', str),
        'route_id': ('idRoute', int),
        'driver_id': ('idDriver', str),
        'driver_fio': ('driverFio', str),
        'date_begin': ('dateBegin', parse_datetime),
        'date_end': ('dateEnd', parse_datetime),
        'return_time': ('returnTime', parse_datetime),
        'leave_time': ('leaveTime', parse_datetime)
    }
    model = models.Job

    def post(self, request, *args, **kwargs):
        jobs = []
        jobs_els = request.data.xpath('/setJobs/job')

        if jobs_els:

            for j in jobs_els:
                data = parse_xml_input_data(request, self.model_mapping, j)

                name = data.get('name')
                if not name:
                    return error_response('Не указан параметр jobName', code='jobName_not_found')

                routes_ids = [x['id'] for x in get_routes(user=request.user)]
                if data['route_id'] not in routes_ids:
                    return error_response(
                        'Шаблон задания idRoute неверный или не принадлежит текущей организации',
                        code='route_permission'
                    )

                data['user'] = request.user

                units = get_units(user=request.user)
                routes = get_routes(user=request.user, with_points=True)

                units_cache = {
                    u['id']: '%s (%s) [%s]' % (u['name'], u['number'], u['vin'])
                    for u in units
                }
                routes_cache = {r['id']: r for r in routes}

                try:
                    data['unit_title'] = units_cache.get(int(data['unit_id']))
                except (ValueError, TypeError, AttributeError):
                    pass

                try:
                    data['route_title'] = routes_cache.get(int(data['route_id']), {}).get('name')
                except (ValueError, TypeError, AttributeError):
                    pass

                self.job = self.model.objects.create(**data)

                try:
                    register_job_notifications(self.job, routes_cache=routes_cache)
                except Exception as e:
                    # TODO: убрать исключение, когда все точно заработает
                    print(e)

                jobs.append(self.job)

        context = self.get_context_data(**kwargs)
        context.update({
            'now': utcnow(),
            'acceptedJobs': jobs
        })

        return XMLResponse('ura/ackjobs.xml', context)
