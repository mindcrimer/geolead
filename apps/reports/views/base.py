# -*- coding: utf-8 -*-
from django.contrib import messages
from django.contrib.messages import get_messages

from snippets.utils.datetime import utcnow
from snippets.views import BaseTemplateView


WIALON_INTERNAL_EXCEPTION = \
    'Произошла ошибка при получении данных. ' \
    'Пожалуйста, повторите ваш запрос позже или сократите период отчета.'

WIALON_NOT_LOGINED = 'Вы не выполнили вход через Wialon'
WIALON_USER_NOT_FOUND = 'Не передан идентификатор пользователя'
WIALON_FORM_ERRORS = 'Обнаружены ошибки формы'


class ReportException(Exception):
    pass


class BaseReportView(BaseTemplateView):
    """Базовый класс отчета"""
    form = None
    report_name = ''

    def get_default_context_data(self, **kwargs):
        context = {
            'None': None,
            'report_data': None,
            'report_name': self.report_name,
            'messages': get_messages(self.request) or []
        }

        data = self.request.POST if self.request.method == 'POST' else {
            'dt_from': utcnow().replace(hour=0, minute=0, second=0),
            'dt_to': utcnow().replace(hour=23, minute=59, second=59),
            'sid': self.request.GET.get('sid', ''),
            'user': self.request.GET.get('user', '')
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
            raise ReportException(WIALON_FORM_ERRORS + ' ' + kwargs['form'].errors)

        kwargs['sess_id'] = self.request.GET.get('sid', '')
        kwargs['username'] = self.request.GET.get('user', '')

        if not kwargs['sess_id']:
            raise ReportException(WIALON_NOT_LOGINED)

        if not kwargs['username']:
            raise ReportException(WIALON_USER_NOT_FOUND)

        return kwargs
