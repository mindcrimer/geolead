# -*- coding: utf-8 -*-
import datetime
import time

import xlwt
from django.contrib import messages
from django.contrib.messages import get_messages
from django.http import HttpResponse
from django.utils.timezone import utc

import ujson

from base.exceptions import ReportException
from snippets.views import BaseTemplateView
from wialon.exceptions import WialonException

WIALON_INTERNAL_EXCEPTION = \
    'Произошла ошибка при получении данных. ' \
    'Пожалуйста, повторите ваш запрос позже или сократите период отчета. Ошибка: %s'

WIALON_NOT_LOGINED = 'Вы не выполнили вход через Wialon'
WIALON_USER_NOT_FOUND = 'Не передан идентификатор пользователя'
WIALON_FORM_ERRORS = 'Обнаружены ошибки формы'


class BaseReportView(BaseTemplateView):
    """Базовый класс отчета"""
    form = None
    report_name = ''
    context_dump_fields = ('report_data',)

    def get_default_context_data(self, **kwargs):
        context = {
            'None': None,
            'report_data': None,
            'report_name': self.report_name,
            'messages': get_messages(self.request) or [],
            'sid': self.request.session.get('sid', ''),
            'user': self.request.session.get('user', '')
        }

        data = self.request.POST if self.request.method == 'POST' else {
            'dt_from': datetime.datetime.now().replace(hour=0, minute=0, second=0, tzinfo=utc),
            'dt_to': datetime.datetime.now().replace(hour=23, minute=59, second=59, tzinfo=utc)
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
        if 'download' in request.GET:
            return self.download_xls(request, *args, **kwargs)
        try:
            context = self.get_context_data(**kwargs)
            # if context['report_data']:
            #     key = 'context_%s' % self.report_name
            #     dump_context = self.get_dump_context(context)
            #     request.session[key] = ujson.dumps(dump_context)

        except (ReportException, WialonException) as e:
            messages.error(request, str(e))
            context = super(BaseReportView, self).get_context_data(**kwargs)
            context = self.get_default_context_data(**context)
            return self.render_to_response(context)

        return self.render_to_response(context)

    def get_dump_context(self, context):
        return {x: y for x, y in context.items() if x in self.context_dump_fields}

    def download_xls(self, request, *args, **kwargs):
        key = 'context_%s' % self.report_name

        context = request.session.get(key)
        if not context:
            messages.error(request, 'Данные отчета не найдены')
            context = super(BaseReportView, self).get_context_data(**kwargs)
            context = self.get_default_context_data(**context)
            return self.render_to_response(context)

        context = ujson.loads(context)
        filename = '%s_%s.xls' % (self.report_name, int(time.time()))

        workbook = xlwt.Workbook()
        worksheet = workbook.add_sheet('Отчет')

        self.write_xls_data(worksheet, context)

        response = HttpResponse(mimetype="application/ms-excel")
        response['Content-Disposition'] = 'attachment; filename=%s' % filename
        workbook.save(response)
        return response

    def write_xls_data(self, worksheet, context):
        return worksheet

    def get_context_data(self, **kwargs):
        kwargs = super(BaseReportView, self).get_context_data(**kwargs)
        kwargs.update(self.get_default_context_data(**kwargs))

        if not kwargs['form'].is_valid():
            errors = str(kwargs['form'].errors)
            if 'sid' in errors:
                raise ReportException(
                    WIALON_FORM_ERRORS + '. Возможно, вы не совершили вход через Wialon / APPS'
                )

            if 'user' in errors:
                raise ReportException(
                    WIALON_FORM_ERRORS + '. Возможно, имя пользователя из Wialon не совпадает.'
                )

        kwargs['sess_id'] = self.request.session.get('sid', '')
        kwargs['username'] = self.request.session.get('user', '')

        if not kwargs['sess_id']:
            raise ReportException(WIALON_NOT_LOGINED)

        if not kwargs['username']:
            raise ReportException(WIALON_USER_NOT_FOUND)

        return kwargs
