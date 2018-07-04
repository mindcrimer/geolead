from django.core.management.base import BaseCommand

from notifications.models import Notification
from snippets.utils.datetime import utcnow
from wialon.api.notifications import remove_notification
from wialon.auth import get_wialon_session_key, logout_session
from wialon.exceptions import WialonException


def remove_expired_notifications():
    print('Cleaning expired notifications...')
    # удаляем старые шаблоны уведомлений
    notifications = Notification.objects\
        .filter(expired_at__lt=utcnow())\
        .select_related('job', 'job__user')

    session_cache = {}

    i = 0
    for notification in notifications.iterator():
        user = notification.job.user
        if user not in session_cache:
            sess_id = get_wialon_session_key(user)
            session_cache[user] = sess_id
        else:
            sess_id = session_cache[user]

        try:
            remove_notification(notification, user, sess_id)
        except WialonException as e:
            print(e)
        else:
            notification.delete()
        i += 1

    for user, sess_id in session_cache.items():
        logout_session(user, sess_id)

    print('%s expired notifications removed' % i)


class Command(BaseCommand):
    def handle(self, *args, **options):
        return remove_expired_notifications()
