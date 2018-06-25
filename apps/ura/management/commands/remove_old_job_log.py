import datetime

from django.core.management.base import BaseCommand

from snippets.utils.datetime import utcnow
from ura.models import JobLog


def remove_old_job_log():
    print('Removing old records...')

    until = utcnow() - datetime.timedelta(days=31)
    print('Until %s' % until)
    res = JobLog.objects.filter(created__lt=until).delete()
    print('%s records removed' % res[0])


class Command(BaseCommand):
    def handle(self, *args, **options):
        return remove_old_job_log()
