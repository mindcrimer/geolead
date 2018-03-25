# -*- coding: utf-8 -*-
import traceback
from smtplib import SMTPException
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
from ura.models import JobLog
from ura.utils import get_organization_user
from wialon.exceptions import WialonException


@method_decorator(csrf_exempt, name='dispatch')
class URAResource(TemplateView):
    authenticate_as_supervisor = False
    template_engine = 'jinja2'
    content_type = 'application/json'
    http_method_names = ['get', 'post', 'put', 'patch', 'delete', 'head', 'options', 'trace']

    def __init__(self, *args, **kwargs):
        super(URAResource, self).__init__(*args, **kwargs)
        self.job = None

    def pre_view_trigger(self, request, **kwargs):
        pass

    def dispatch_method(self, request, *args, **kwargs):
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
                return error_response(
                    str(e),
                    status=403,
                    code=getattr(e, 'code', None)
                )

        try:
            self.pre_view_trigger(request, **kwargs)
        except APIProcessError as e:
            return error_response(
                str(e),
                status=e.http_status if e.http_status else None,
                code=e.code
            )
        except (ValueError, IndexError, KeyError, AttributeError, TypeError) as e:
            if not settings.DEBUG:
                try:
                    send_trigger_email(
                        'Ошибка в работе интеграции Wialon', extra_data={
                            'POST': request.body,
                            'Exception': str(e),
                            'Traceback': traceback.format_exc()
                        }
                    )
                except (ConnectionError, SMTPException):
                    pass

                return error_response(
                    'Ошибка входящих данных из источника данных. '
                    'Попробуйте повторить запрос позже.',
                    status=400,
                    code='source_data_invalid'
                )
            raise

        except Exception as e:
            try:
                send_trigger_email(
                    'Ошибка в работе интеграции Wialon', extra_data={
                        'POST': request.body,
                        'Exception': str(e),
                        'Traceback': traceback.format_exc()
                    }
                )
            except (ConnectionError, SMTPException):
                pass

            return error_response(
                'Внутренняя ошибка сервера',
                status=500,
                code='internal_server_error'
            )

        attempts = 0
        attempts_limit = 20
        last_error = ''
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

            except WialonException as e:
                last_error = str(e)
                attempts += 1
                print('Инициирую новую попытку доступа к Wialon')
                # после каждого падения Виалона ждет 5 секунд и повторяем попытку
                sleep(5)

            except (ValueError, IndexError, KeyError, AttributeError, TypeError) as e:
                if not settings.DEBUG:
                    try:
                        send_trigger_email(
                            'Ошибка в работе интеграции Wialon', extra_data={
                                'POST': request.body,
                                'Exception': str(e),
                                'Traceback': traceback.format_exc()
                            }
                        )
                    except (ConnectionError, SMTPException):
                        pass

                    return error_response(
                        'Ошибка входящих данных из источника данных. '
                        'Попробуйте повторить запрос позже',
                        status=400,
                        code='source_data_invalid'
                    )
                raise

            except Exception as e:
                try:
                    send_trigger_email(
                        'Ошибка в работе интеграции Wialon', extra_data={
                            'POST': request.body,
                            'Exception': str(e),
                            'Traceback': traceback.format_exc()
                        }
                    )
                except (ConnectionError, SMTPException):
                    pass

                return error_response(
                    'Внутренняя ошибка сервера',
                    status=500,
                    code='internal_server_error'
                )

        return error_response(
            'Лимит попыток обращения в Wialon (%s) закончился. %s' % (
                attempts_limit, last_error
            ),
            status=400,
            code='attempts_limit'
        )

    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        response = self.dispatch_method(request, *args, **kwargs)
        user = request.user if request.user.is_authenticated() else None

        JobLog.objects.create(
            job=self.job,
            url=self.request.path_info,
            request=self.request.body.decode('cp1251'),
            user=user,
            response=response.rendered_content,
            response_status=response.status_code
        )
        return response

    def authenticate(self, request):
        username, password = extract_token_from_request(request)
        supervisor = authenticate_credentials(username, password)

        if self.authenticate_as_supervisor:
            return supervisor

        org_id = None
        if request.data:
            try:
                org_id = int(request.data.getroot().get('idOrg'))
            except (TypeError, ValueError):
                pass

        user = get_organization_user(supervisor, org_id)

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
            raise APIParseError(
                _('Отправлены неправильные данные XML'), code='invalid_request_body_received'
            )

    def get_context_data(self, **kwargs):
        context = super(URAResource, self).get_context_data(**kwargs)
        context['request'] = self.request
        return context
