# -*- coding: utf-8 -*-
from django.contrib import messages
from django.contrib.messages import get_messages
from snippets.utils.datetime import utcnow

from snippets.views import BaseTemplateView


WIALON_INTERNAL_EXCEPTION = \
    'Произошла ошибка при получении данных. ' \
    'Пожалуйста, повторите ваш запрос позже или сократите период отчета.'


class ReportException(Exception):
    pass


class BaseReportView(BaseTemplateView):
    """Базовый класс отчета"""
    form = None

    def get_default_context_data(self, **kwargs):
        context = {
            'None': None,
            'report_data': None,
            'messages': get_messages(kwargs['view'].request) or []
        }

        data = kwargs['view'].request.POST if kwargs['view'].request.method == 'POST' else {
            'dt_from': utcnow().replace(hour=0, minute=0, second=0),
            'dt_to': utcnow().replace(hour=23, minute=59, second=59)
        }
        form = self.form(data)

        form.is_valid()
        context['form'] = form

        return context

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

        return kwargs
