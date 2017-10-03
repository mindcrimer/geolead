# -*- coding: utf-8 -*-
import datetime

from django.contrib import messages
from django.contrib.messages import get_messages
from django.utils.timezone import utc

from base.exceptions import ReportException
from snippets.views import BaseTemplateView


WIALON_INTERNAL_EXCEPTION = \
    'Произошла ошибка при получении данных. ' \
    'Пожалуйста, повторите ваш запрос позже или сократите период отчета.'

WIALON_NOT_LOGINED = 'Вы не выполнили вход через Wialon'
WIALON_USER_NOT_FOUND = 'Не передан идентификатор пользователя'
WIALON_FORM_ERRORS = 'Обнаружены ошибки формы'


class BaseReportView(BaseTemplateView):
    """Базовый класс отчета"""
    form = None
    report_name = ''

    def get_default_context_data(self, **kwargs):
        context = {
            'None': None,
            'report_data': None,
            'report_name': self.report_name,
            'messages': get_messages(self.request) or [],
            'sid': self.request.GET.get('sid', ''),
            'user': self.request.GET.get('user', '')
        }

        data = self.request.POST if self.request.method == 'POST' else {
            'dt_from': datetime.datetime.now().replace(hour=0, minute=0, second=0, tzinfo=utc),
            'dt_to': datetime.datetime.now().replace(hour=23, minute=59, second=59, tzinfo=utc),
            'sid': context['sid'],
            'user': context['user']
        }
        form = self.form(data)

        context['form'] = form

        return context

    def get(self, request, *args, **kwargs):
        try:
            return super(BaseReportView, self).get(request, *args, **kwargs)
        except ReportException as e:
            messages.error(request, str(e))
            context = super(BaseReportView, self).get_context_data(**kwargs)
            context = self.get_default_context_data(**context)
            return self.render_to_response(context)

    def post(self, request, *args, **kwargs):
        try:
            context = self.get_context_data(**kwargs)
        except ReportException as e:
            messages.error(request, str(e))
            context = super(BaseReportView, self).get_context_data(**kwargs)
            context = self.get_default_context_data(**context)
            return self.render_to_response(context)

        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        kwargs = super(BaseReportView, self).get_context_data(**kwargs)
        kwargs.update(self.get_default_context_data(**kwargs))

        if not kwargs['form'].is_valid():
            errors = str(kwargs['form'].errors)
            if 'sid' in errors:
                raise ReportException(
                    WIALON_FORM_ERRORS + '. Возможно, вы совершили вход не через Wialon.'
                )

            if 'user' in errors:
                raise ReportException(
                    WIALON_FORM_ERRORS + '. Возможно, имя пользователя из Wialon не совпадает.'
                )

        kwargs['sess_id'] = self.request.GET.get('sid', '')
        kwargs['username'] = self.request.GET.get('user', '')

        if not kwargs['sess_id']:
            raise ReportException(WIALON_NOT_LOGINED)

        if not kwargs['username']:
            raise ReportException(WIALON_USER_NOT_FOUND)

        return kwargs