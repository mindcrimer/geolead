# -*- coding: utf-8 -*-
from datetime import datetime

from django.template.defaultfilters import floatformat

from base.exceptions import APIProcessError, AuthenticationFailed
from reports.utils import local_to_utc_time
from users.models import User


def float_format(value, arg=0):
    return floatformat(value, arg).replace(',', '.')


def parse_datetime(str_date, timezone):
    local_dt = datetime.strptime(str_date, '%d.%m.%Y %H:%M:%S')
    return local_to_utc_time(local_dt, timezone)


def get_organization_user(supervisor, org_id):
    if not org_id:
        raise AuthenticationFailed('Не указан параметр idOrg', code='idOrg_not_found')

    try:
        user = User.objects.filter(is_active=True, wialon_token__isnull=False).get(pk=org_id)
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
                data[k] = v[1](element.get(v[0]), request.user.ura_tz)
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
