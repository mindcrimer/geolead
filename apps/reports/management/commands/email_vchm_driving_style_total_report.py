import datetime
from time import sleep
import traceback

from django.core.files.base import ContentFile
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
TIMEOUT = 60 * 60 * 24
URL = '/vchm/driving_style/'


def make_report(report, user, sess_id, date_from, date_to, attempts=0):
    if attempts > 10:
        raise WialonException('Не удалось получить отчет из-за ошибок Виалона')

    s = requests.Session()
    s.headers.update({'referer': SITE_URL})
    url = '%s/' % SITE_URL
    print(url)
    s.get(
        url,
        params={'sid': sess_id, 'user': user.username},
        timeout=TIMEOUT,
        verify=False
    )
    url = '%s%s' % (SITE_URL, URL)
    print(url)
    res = s.post(url, data={
        'dt_from': date_from.strftime('%d.%m.%Y'),
        'dt_to': date_to.strftime('%d.%m.%Y'),
        'total_report': '1'
    }, timeout=TIMEOUT, verify=False)

    if 'error\': ' in res.text or 'ошибка\': ' in res.text.lower():
        attempts += 1
        print('Wialon error: %s. Attempt %s. Waiting...' % (res.text, attempts))
        sleep(10)
        return make_report(report, user, sess_id, date_from, date_to, attempts=attempts)

    return res


def email_reports():
    print('Mailing monthly driving style total report...')
    reports = models.DrivingStyleTotalReportDelivery.objects.published()

    now = utcnow()

    for report in reports:
        print('Monthly VCHM Driving style total report %s' % report)

        for user in report.users.all():
            local_now = utc_to_local_time(now, user.timezone)

            if not user.email:
                print('Skipping user %s (no email)' % user)
                continue

            print('User %s' % user)
            sess_id = None

            try:
                # получаем отчеты через HTTP
                sess_id = get_wialon_session_key(user)
                # если время выполнения - 1е число месяца, то отчет сформируется за прошлый месяц,
                # иначе отчет подготовится за текущий месяц вчерашний день включительно.
                date_to = (local_now - datetime.timedelta(days=1)).date()
                date_from = date_to.replace(day=1)

                res = make_report(
                    report, user, sess_id, date_from=date_from, date_to=date_to, attempts=0
                )

                filename = 'total_vchm_driving_report_%s.xls' % user.pk
                log = models.ReportEmailDeliveryLog(
                    user=user,
                    email=user.email,
                    report_type=EmailDeliveryReportTypeEnum.DRIVING_STYLE,
                    subject='Сводный отчет о качестве вождения (ВЧМ)',
                    body='Здравствуйте, %s. Отчет по вложении.' % user.full_name
                )
                content = ContentFile(res.content)
                log.report.save(filename, content, save=False)
                log.save()
                log.send(reraise=True)

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
    """
    Сводный отчет по БДД. Вызывается раз в месяц.
    Проверки на текущий час нет, так как в планировщике указывается конкретный час выполнения
    """

    def handle(self, *args, **options):
        return email_reports()
