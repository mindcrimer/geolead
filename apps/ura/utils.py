import datetime

from django.template.defaultfilters import floatformat

from base.exceptions import APIProcessError, AuthenticationFailed
from notifications.exceptions import NotificationError
from notifications.models import Notification
from notifications import notifications
from reports.utils import local_to_utc_time
from ura.models import StandardJobTemplate
from users.models import User


def float_format(value, arg=0):
    return floatformat(value, arg).replace(',', '.')


def parse_datetime(str_date, timezone):
    local_dt = datetime.datetime.strptime(str_date, '%d.%m.%Y %H:%M:%S')
    return local_to_utc_time(local_dt, timezone)


def get_organization_user(supervisor, org_id):
    if not org_id:
        raise AuthenticationFailed('Не указан параметр idOrg', code='idOrg_not_found')

    try:
        user = User.objects.filter(is_active=True).get(pk=org_id)
    except User.DoesNotExist:
        raise AuthenticationFailed('Организация не найдена', code='org_not_found')

    if user.pk != supervisor.pk and user.supervisor_id != supervisor.pk:
        raise AuthenticationFailed('Нет доступа к данной организации', code='org_forbidden')

    return user


def parse_xml_input_data(request, mapping, element, preserve_tzinfo=False):
    data = {}
    for k, v in mapping.items():
        try:
            if v[1] == parse_datetime:
                data[k] = v[1](element.get(v[0]), request.user.timezone)
                if not preserve_tzinfo:
                    data[k] = data[k].replace(tzinfo=None)
            else:
                data[k] = v[1](element.get(v[0]))
        except (ValueError, TypeError):
            raise APIProcessError(
                'Ошибка при извлечении данных. Параметр %s, значение %s' % (
                    v[0], element.get(v[0])
                ),
                http_status=400,
                code='input_data_invalid'
            )

    return data


def is_fixed_route(route_title):
    return route_title and 'фиксирован' in route_title.lower()


def register_job_notifications(job, sess_id, routes_cache=None):
    """Регистрация всех шаблонов уведомлений при создании путевого листа"""
    # Если название шаблона задания известно и он не фиксированный
    if not job.route_title or is_fixed_route(job.route_title):
        return False

    results = []

    available_notification_backends = (
        # 1. Съезд с маршрута
        notifications.route_coming_off_notification,
        # 2. Перепростой вне планового маршрута
        notifications.space_overstatements_notification,
        # 3. Перепростой на маршруте
        notifications.route_overparking_notification,
        # 4. Превышение времени нахождения на погрузке
        notifications.load_overtime_notification,
        # 5. Превышение времени нахождения на разгрузке
        notifications.unload_overtime_notification,
        # 6. Нахождение объекта вне планового маршрута
        notifications.space_notification,
        # 7. Превышение времени нахождения на маршруте
        notifications.route_overstatement_notification
    )

    job_template = StandardJobTemplate.objects.filter(wialon_id=job.route_id).first()

    for backend in available_notification_backends:
        try:
            result = backend(job, sess_id, routes_cache=routes_cache, job_template=job_template)
            results.extend(tuple(result))
        except NotificationError as e:
            print(str(e))

    for wialon_id, received_data, sent_data in results:
        Notification.objects.create(
            job=job,
            wialon_id=wialon_id,
            sent_data=sent_data,
            received_data=received_data,
            expired_at=job.date_end + datetime.timedelta(seconds=60 * 10)
        )

    return True
