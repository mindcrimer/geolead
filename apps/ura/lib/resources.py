# -*- coding: utf-8 -*-
from django.contrib.auth.models import AnonymousUser
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView

from lxml import etree
from lxml.etree import ParseError
from six import BytesIO

from ura.lib.exceptions import APIParseError, AuthenticationFailed, AuthenticationExpired, \
    AuthenticationLoginRequired, APIValidationError, APIProcessError
from ura.lib.response import error_response, validation_error_response
from ura.lib.utils import extract_token_from_request, authenticate_credentials


@method_decorator(csrf_exempt, name='dispatch')
class URAResource(TemplateView):
    template_engine = 'jinja2'
    content_type = 'application/json'
    http_method_names = ['get', 'post', 'put', 'patch', 'delete', 'head', 'options', 'trace']

    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        method = request.method.lower()
        if method in self.http_method_names:
            handler = getattr(self, method, self.http_method_not_allowed)
        else:
            handler = self.http_method_not_allowed

        # для изменяющих методов подставим json данные в request.data
        if method in ('post', 'put', 'patch', 'delete'):
            if request.body:
                try:
                    request.data = self.parse_raw_data(request)
                except APIParseError as e:
                    return error_response(str(e), code=getattr(e, 'code', None))
            else:
                request.data = None

        request.user = AnonymousUser()
        # если метод не 405 и не публичный, проверяем авторизацию
        # публичные эндпоинты вообще не проверяем, это может пойти им во вред
        if handler != self.http_method_not_allowed \
                and not getattr(handler, 'is_public_http_method', False):
            try:
                request.user = self.authenticate(request)

            except AuthenticationFailed as e:
                # обновлять токен не имеет смысла, он неправильный. Просим войти заново.
                return error_response(str(e), status=403, code=getattr(e, 'code', None))

            except AuthenticationExpired as e:
                # токен устарел, можно обновить токен
                return error_response(str(e), status=401, code=getattr(e, 'code', None))

            except AuthenticationLoginRequired as e:
                # токен окончательно устарел, долго не пользовались. Требуется войти заново.
                return error_response(
                    str(e),
                    status=403,
                    code='token_expired'
                )

        try:
            return handler(request, *args, **kwargs)

        except APIValidationError as e:
            return validation_error_response(e.messages)

        except APIProcessError as e:
            return error_response(
                str(e),
                status=e.http_status if e.http_status else None,
                code=e.code
            )

    @staticmethod
    def authenticate(request):
        user, password = extract_token_from_request(request)
        user = authenticate_credentials(user, password)

        return user

    def http_method_not_allowed(self, request, *args, **kwargs):
        return error_response(
            _('Метод не разрешен (%s): %s') % (request.method, request.path),
            status=405,
            code='method_not_allowed'
        )

    @staticmethod
    def parse_raw_data(request):
        try:
            return etree.parse(BytesIO(request.body))

        except ParseError:
            APIParseError(
                _('Отправлены неправильные данные'), code='invalid_request_body_received'
            )
