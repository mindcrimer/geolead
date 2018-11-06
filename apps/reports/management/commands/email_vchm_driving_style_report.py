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
URL = '/vchm/driving_style/'
timeout = 60 * 60 * 24


def make_report(report, user, sess_id, date_from, date_to, attempts=0):
    if attempts > 5:
        raise WialonException('Не удалось получить отчет из-за ошибок Виалона')

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
    url = '%s%s' % (SITE_URL, URL)
    print(url)
    res = s.post(url, data={
        'dt_from': date_from.strftime('%d.%m.%Y'),
        'dt_to': date_to.strftime('%d.%m.%Y')
    }, timeout=timeout, verify=False)

    if 'error\': ' in res.text:
        print('Wialon error. Waiting...')
        sleep(5)
        return make_report(report, user, sess_id, date_from, date_to, attempts=attempts + 1)

    return res


def email_reports(period=None):
    print('Mailing %s driving style report...' % period)
    if not period or period not in ('daily', 'weekly', 'monthly'):
        print('Period not specified')
        return

    reports = models.DrivingStyleReportDelivery.objects.published()
    period_verbose = ''
    if period == 'daily':
        period_verbose = 'Ежедневный'
        reports = reports.filter(is_daily=True)
    elif period == 'weekly':
        period_verbose = 'Еженедельный'
        reports = reports.filter(is_weekly=True)
    elif period == 'monthly':
        period_verbose = 'Ежемесячный'
        reports = reports.filter(is_monthly=True)

    now = utcnow()

    for report in reports:
        print('%s VCHM Driving style report %s' % (period, report))

        for user in report.users.all():
            local_now = utc_to_local_time(now, user.timezone)
            if not user.email:  # or local_now.hour != 5:
                print('Skipping user %s' % user)
                continue

            print('User %s' % user)
            sess_id = None

            try:
                # получаем отчеты через HTTP
                sess_id = get_wialon_session_key(user)
                date_from = date_to = (local_now - datetime.timedelta(days=1)).date()

                if period == 'daily':
                    date_from = date_to
                elif period == 'weekly':
                    date_from = (local_now - datetime.timedelta(days=7)).date()
                elif period == 'monthly':
                    date_from = date_to.replace(day=1)

                res = make_report(
                    report, user, sess_id, date_from=date_from, date_to=date_to, attempts=0
                )

                mail = EmailMessage(
                    '%s отчет о качестве вождения (ВЧМ)' % period_verbose,
                    'Здравствуйте, %s. Отчет по вложении.' % user.full_name,
                    to=['wizzzet@gmail.com']  # user.email
                )
                filename = '%s_vchm_driving_report_%s.xls' % (period, user.pk)
                mail.attach(filename, res.content, 'application/vnd.ms-excel')
                mail.send()
                print('Email sent.')

                log = models.ReportEmailDeliveryLog(
                    user=user,
                    email=user.email,
                    report_type=EmailDeliveryReportTypeEnum.DRIVING_STYLE,
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
    def add_arguments(self, parser):
        parser.add_argument(
            '--period',
            dest='period',
            help='period [daily|weekly|monthly]',
        )

    def handle(self, *args, **options):
        return email_reports(options.get('period'))
