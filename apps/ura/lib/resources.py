# -*- coding: utf-8 -*-
from time import sleep

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView

from lxml import etree
from lxml.etree import ParseError
from six import BytesIO

from base.exceptions import APIParseError, AuthenticationFailed, APIValidationError, \
    APIProcessError
from snippets.utils.email import send_trigger_email
from ura.lib.response import error_response, validation_error_response
from ura.lib.utils import extract_token_from_request, authenticate_credentials
from wialon.exceptions import WialonException


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

        attempts = 0
        attempts_limit = 20
        while attempts < attempts_limit:
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

            except WialonException:
                attempts += 1
                # после каждого падения Виалона ждет 5 секунд и повторяем попытку
                sleep(5)

            except (ValueError, IndexError, KeyError, AttributeError, TypeError):
                if not settings.DEBUG:
                    send_trigger_email(
                        'Ошибка в работе интеграции WIalon', extra_data={
                            'POST': request.body
                        }
                    )

                    return error_response(
                        'Ошибка входящих данных из источника данных. '
                        'Попробуйте повторить запрос позже',
                        status=400,
                        code='source_data_invalid'
                    )
                raise

        return error_response(
            'Лимит попыток обращения к источнику данных (%s попыток) закончился' % attempts_limit,
            status=400,
            code='attempts_limit'
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

        except ParseError as e:
            raise APIParseError(
                _('Отправлены неправильные данные'), code='invalid_request_body_received'
            )

    def get_context_data(self, **kwargs):
        context = super(URAResource, self).get_context_data(**kwargs)
        context['request'] = self.request
        return context
