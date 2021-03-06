from snippets.utils.datetime import utcnow
from ura import models
from ura.lib.resources import URAResource
from ura.lib.response import error_response, XMLResponse
from ura.utils import parse_datetime, parse_xml_input_data


class URABreakJobsResource(URAResource):
    model_mapping = {
        'date_begin': ('dateBegin', parse_datetime),
        'date_end': ('dateEnd', parse_datetime),
        'new_date_end': ('newDateEnd', parse_datetime),
        'job_id': ('idJob', int),
    }
    model = models.Job

    def post(self, request, *args, **kwargs):
        jobs = []
        jobs_els = request.data.xpath('/breakJobs/job')

        if jobs_els:

            for j in jobs_els:
                data = parse_xml_input_data(request, self.model_mapping, j)

                job_id = data.pop('job_id')
                if not job_id:
                    return error_response('Не указан параметр idJob', code='idJob_not_found')

                if data.get('new_date_end') and data['new_date_end'] <= data['date_begin']:
                    self.model.objects.filter(pk=job_id).delete()
                else:
                    try:
                        self.job = self.model.objects.get(pk=job_id)
                    except self.model.DoesNotExist:
                        return error_response(
                            'Задание с ID=%s не найдено' % job_id, code='job_not_found'
                        )

                    for k, v in data.iems():
                        if k == 'new_date_end':
                            k = 'date_end'
                        elif k == 'date_end' and 'new_date_end' in data and data['new_date_end']:
                            continue

                        setattr(self.job, k, v)
                        self.job.save()
                    jobs.append(self.job)

        context = self.get_context_data(**kwargs)
        context.update({
            'now': utcnow(),
            'breakJobs': jobs
        })

        return XMLResponse('ura/ackBreakJobs.xml', context)
