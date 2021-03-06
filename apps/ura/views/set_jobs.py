from snippets.utils.datetime import utcnow
from ura import models
from ura.lib.resources import URAResource
from ura.lib.response import XMLResponse, error_response
from ura.utils import parse_xml_input_data, parse_datetime, register_job_notifications
from wialon.api import get_routes, get_units
from wialon.auth import get_wialon_session_key, logout_session


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
        sess_id = get_wialon_session_key(request.user)

        if jobs_els:

            for j in jobs_els:
                data = parse_xml_input_data(request, self.model_mapping, j)

                name = data.get('name')
                if not name:
                    logout_session(request.user, sess_id)
                    return error_response('Не указан параметр jobName', code='jobName_not_found')

                routes = get_routes(sess_id, with_points=True)
                units = get_units(sess_id)

                routes_ids = [x['id'] for x in routes]
                if data['route_id'] not in routes_ids:
                    return error_response(
                        'Шаблон задания idRoute неверный или не принадлежит текущей организации',
                        code='route_permission'
                    )

                units_cache = {
                    u['id']: '%s (%s) [%s]' % (u['name'], u['number'], u['vin'])
                    for u in units
                }

                try:
                    data['unit_title'] = units_cache.get(int(data['unit_id']))
                except (ValueError, TypeError, AttributeError):
                    pass

                if not data['unit_title']:
                    return error_response(
                        'Объект ID=%s не найден в текущем ресурсе организации' % data['unit_id'],
                        code='unit_not_found_permission'
                    )

                routes_cache = {r['id']: r for r in routes}
                try:
                    data['route_title'] = routes_cache.get(int(data['route_id']), {}).get('name')
                except (ValueError, TypeError, AttributeError):
                    pass

                data['user'] = request.user
                self.job = self.model.objects.create(**data)
                register_job_notifications(self.job, sess_id, routes_cache=routes_cache)
                logout_session(request.user, sess_id)
                jobs.append(self.job)

        context = self.get_context_data(**kwargs)
        context.update({
            'now': utcnow(),
            'acceptedJobs': jobs
        })

        return XMLResponse('ura/ackjobs.xml', context)
