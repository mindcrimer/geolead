import datetime
import traceback
from time import sleep

from django.core.files.base import ContentFile
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand

import requests

from reports import models
from reports.enums import EmailDeliveryReportTypeEnum
from reports.utils import utc_to_local_time
from snippets.utils.datetime import utcnow
from snippets.utils.email import send_trigger_email
from wialon.auth import get_wialon_session_key, logout_session
from wialon.exceptions import WialonException

SITE_URL = 'http://127.0.0.1'
URL = '/faults/'
timeout = 60 * 60 * 24


def make_report(report, user, sess_id, attempts=0):
    if attempts > 5:
        raise WialonException('Не удалось получить отчет из-за ошибок Виалона')

    now = utcnow()
    local_now = utc_to_local_time(now, user.timezone)
    ura_user = user.ura_user if user.ura_user_id else user
    s = requests.Session()
    s.headers.update({'referer': SITE_URL})
    url = '%s/' % SITE_URL
    print(url)
    s.get(
        url,
        params={'sid': sess_id, 'user': ura_user.username},
        timeout=timeout,
        verify=False
    )

    yesterday = (local_now - datetime.timedelta(days=1)).date()
    url = '%s%s' % (SITE_URL, URL)
    print(url)
    res = s.post(url, data={
        'dt': yesterday.strftime('%d.%m.%Y'),
        'job_extra_offset': str(report.job_extra_offset)
    }, timeout=timeout, verify=False)

    if 'error\': ' in res.text:
        print('Wialon error. Waiting...')
        sleep(5)
        return make_report(report, user, sess_id, attempts=attempts + 1)

    return s


def email_reports():
    print('Mailing faults report...')
    reports = models.FaultsReportDelivery.objects.published()

    now = utcnow()

    for report in reports:
        print('Faults report %s' % report)

        for user in report.users.all():
            local_now = utc_to_local_time(now, user.timezone)
            if not user.email or local_now.hour != 5:
                print('Skipping user %s' % user)
                continue

            print('User %s' % user)
            sess_id = None

            try:
                # получаем отчеты через HTTP
                sess_id = get_wialon_session_key(user)
                s = make_report(report, user, sess_id, attempts=0)
                url = '%s%s' % (SITE_URL, URL)
                print(url + '?download=1')
                res = s.get(
                    url,
                    params={'download': '1'},
                    timeout=timeout,
                    verify=False
                )

                mail = EmailMessage(
                    'Ежедневный отчет о состоянии оборудования',
                    'Здравствуйте, %s. Отчет по вложении.' % user.full_name,
                    to=[user.email]
                )
                filename = 'faults_report_%s.xls' % user.pk
                mail.attach(filename, res.content, 'application/vnd.ms-excel')
                mail.send()
                print('Email sent.')

                log = models.ReportEmailDeliveryLog(
                    user=user,
                    email=user.email,
                    report_type=EmailDeliveryReportTypeEnum.FAULTS,
                )
                content = ContentFile(res.content)
                log.report.save(filename, content)
                log.save()

            except Exception as e:
                print('Error: %s' % e)
                send_trigger_email(
                    'Ошибка в работе системы рассылки отчетов', extra_data={
                        'Exception': str(e),
                        'Traceback': traceback.format_exc(),
                        'report': report,
                        'user': user
                    }
                )
            finally:
                if sess_id:
                    logout_session(user, sess_id)


class Command(BaseCommand):
    def handle(self, *args, **options):
        return email_reports()
