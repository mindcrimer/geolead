import ctypes
import datetime
import traceback

from base.exceptions import APIProcessError
from simplejson.errors import JSONDecodeError
from snippets.utils.email import send_trigger_email
from wialon.exceptions import WialonException


def load_requests_json(result):
    try:
        return result.json()
    except JSONDecodeError as e:
        send_trigger_email(
            'Ошибка в работе интеграции Wialon', extra_data={
                'Exception': str(e),
                'Traceback': traceback.format_exc(),
                'text': result.text
            }
        )
        raise APIProcessError('Не удалось извлечь ответ из Wialon')


def get_wialon_timezone_integer(timezone):
    now = datetime.datetime.now()
    offset = int(timezone.utcoffset(now).total_seconds())
    return ctypes.c_int(offset & 0xf000ffff | 0x08000000).value


def process_error(result, error):
    if 'error' in result:
        if result['error'] == 1:
            raise WialonException(
                error + ' Ошибка: ваша сессия устарела. Зайдите заново в приложение через APPS.'
            )
        raise WialonException(error + (' Ошибка: %s' % result))
