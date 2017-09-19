# -*- coding: utf-8 -*-
from datetime import datetime

from django.utils.timezone import get_current_timezone

from ura.lib.exceptions import APIProcessError
from users.models import User


def parse_datetime(str_date):
    tz = get_current_timezone()
    return tz.localize(datetime.strptime(str_date, '%d.%m.%Y %H:%M:%S'))


def get_organization(request, org_id):
    if not org_id:
        raise APIProcessError('Не указан параметр idOrg', code='idOrg_not_found')

    try:
        user = User.objects.filter(is_active=True, wialon_token__isnull=False).get(pk=org_id)
    except User.DoesNotExist:
        raise APIProcessError('Организация не найдена')

    if user.pk != request.user.pk and user.supervisor_id != request.user.pk:
        raise APIProcessError('Нет доступа к данной организации', code='org_forbidden')

    return user
