import json

from django.conf import settings

import requests

from reports.utils import get_wialon_report_resource_id
from wialon.api import process_error


def remove_notification(notification, user, sess_id):
    r = requests.post(
        settings.WIALON_BASE_URL + '?svc=resource/update_notification&sid=%s' % sess_id, {
            'params': json.dumps({
                'itemId': get_wialon_report_resource_id(user, sess_id),
                'id': notification.wialon_id,
                'callMode': 'delete',
            }),
            'sid': sess_id
        }
    )
    res = r.json()
    process_error(
        res, 'Не удалось удалить шаблон уведомлений ID="%s"' % notification.pk
    )

    return res


def update_notification(request_params, sess_id):
    r = requests.post(
        settings.WIALON_BASE_URL + '?svc=resource/update_notification&sid=%s' % sess_id, {
            'params': json.dumps(request_params),
            'sid': sess_id
        }
    )
    res = r.json()
    action = 'сохранить'
    if request_params.get('callMode', '') == 'delete':
        action = 'удалить'

    process_error(
        res, ('Не удалось %s шаблон уведомлений "%s". Данные: %s' % (
            action, request_params.get('n', ''), request_params
        ))
    )

    return res
