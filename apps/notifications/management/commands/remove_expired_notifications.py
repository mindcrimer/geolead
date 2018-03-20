# -*- coding: utf-8 -*-

from django.core.management.base import BaseCommand

from notifications.models import Notification
from snippets.utils.datetime import utcnow
from wialon.api.notifications import remove_notification
from wialon.exceptions import WialonException


def clear_expired_notifications():
    print('Cleaning expired notifications...')
    # удаляем старые шаблоны уведомлений
    notifications = Notification.objects.filter(expired_at__lt=utcnow()).select_related('job')\
        .filter(job__user__isnull=False)

    i = 0
    for notification in notifications.iterator():
        try:
            remove_notification(notification, user=notification.job.user)
        except WialonException as e:
            print(e)
        else:
            notification.delete()
        i += 1

    print('%s rows deleted' % i)


class Command(BaseCommand):
    def handle(self, *args, **options):
        return clear_expired_notifications()
