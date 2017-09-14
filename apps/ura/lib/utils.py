# -*- coding: utf-8 -*-
from django.utils.translation import ugettext_lazy as _

from ura.lib.exceptions import AuthenticationFailed
from users.models import User


def get_authorization_header(request):
    """Извлекает токен из заголовков запроса (Authorization)"""
    auth = request.META.get('HTTP_AUTHORIZATION', b'')

    if isinstance(auth, str):
        # Work around django test client oddness
        auth = auth.encode('iso-8859-1')

    return auth


def extract_token_from_request(request):
    auth = get_authorization_header(request).decode('utf-8').split(': ')

    if len(auth) == 1:
        raise AuthenticationFailed(
            _('Неправильный заголовок авторизации. Данные не представлены.'),
            code='authorization_header_no_data'
        )
    elif len(auth) > 2:
        raise AuthenticationFailed(
            _('Неправильный заголовок авторизации. Данные не должны содержать комбинацию ": "'),
            code='authorization_header_invalid_data'
        )
    return auth


def authenticate_credentials(username, password):
    """
    Returns an active user that matches the payload's user id and email.
    """
    try:
        user = User.objects.get(username=username)

    except User.DoesNotExist:
        raise AuthenticationFailed(
            _('Пользователь не найден.'),
            code='authorization_header_user_not_found'
        )

    if not user.is_active:
        raise AuthenticationFailed(
            _('Пользователь не активен.'),
            code='authorization_header_user_not_active'
        )

    if not user.check_password(password):
        raise AuthenticationFailed(
            _('Пароль не подходит.'),
            code='authorization_password_invalid'
        )

    return user
