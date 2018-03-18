# -*- coding: utf-8 -*-
import datetime

from django.core.management.base import BaseCommand

from reports.models import WialonReportLog
from snippets.utils.datetime import utcnow


def clear_report_log():
    print('Cleaning report log...')
    # удаляем записи лога запросов отчетов старше 1 часа
    until_dt = utcnow() - datetime.timedelta(seconds=60 * 60)
    result = WialonReportLog.objects.filter(created__lte=until_dt).delete()
    if result[0]:
        print('%s rows deleted' % result[0])


class Command(BaseCommand):
    def handle(self, *args, **options):
        return clear_report_log()
