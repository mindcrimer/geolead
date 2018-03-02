# -*- coding: utf-8 -*-
from django.contrib import messages
from django.contrib.messages import get_messages
from django.http import HttpResponse

import xlwt

from base.exceptions import ReportException
from snippets.utils.datetime import utcnow
from snippets.views import BaseTemplateView
from wialon.exceptions import WialonException

WIALON_INTERNAL_EXCEPTION = \
    'Произошла ошибка при получении данных. ' \
    'Пожалуйста, повторите ваш запрос позже или сократите период отчета. Ошибка: %s'

WIALON_SESSION_EXPIRED = 'Ваша сессия устарела. Зайдите через APPS еще раз.'

WIALON_NOT_LOGINED = 'Вы не выполнили вход через Wialon'
WIALON_USER_NOT_FOUND = 'Не передан идентификатор пользователя'
WIALON_FORM_ERRORS = 'Обнаружены ошибки формы'

REPORT_ROW_HEIGHT = 340


class BaseReportView(BaseTemplateView):
    """Базовый класс отчета"""
    form_class = None
    report_name = ''
    context_dump_fields = ('report_data',)
    can_download = False

    def __init__(self, *args, **kwargs):
        super(BaseReportView, self).__init__(*args, **kwargs)
        self.styles = {}

    def get_default_form(self):
        data = self.request.POST if self.request.method == 'POST' else {}
        return self.form_class(data)

    def get_default_context_data(self, **kwargs):
        context = {
            'can_download': self.can_download,
            'None': None,
            'report_data': None,
            'report_name': self.report_name,
            'messages': get_messages(self.request) or [],
            'sid': self.request.session.get('sid', ''),
            'user': self.request.session.get('user', '')
        }

        form = self.get_default_form()

        context['form'] = form

        return context

    def get(self, request, *args, **kwargs):
        if 'download' in request.GET:
            return self.download_xls(request, *args, **kwargs)

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
            if 'report_data' in context:
                dump_context = self.get_dump_context(context)
                dump_context['cleaned_data'] = context['form'].cleaned_data
                dump_context['stats'] = context.get('stats', {})
                request.session[self.get_session_key()] = dump_context

        except (ReportException, WialonException) as e:
            messages.error(request, str(e))
            context = super(BaseReportView, self).get_context_data(**kwargs)
            context = self.get_default_context_data(**context)
            return self.render_to_response(context)

        return self.render_to_response(context)

    def get_session_key(self):
        return 'context_%s' % self.report_name

    def get_dump_context(self, context):
        return {x: y for x, y in context.items() if x in self.context_dump_fields}

    def download_xls(self, request, *args, **kwargs):
        context = request.session.get(self.get_session_key())
        if not context:
            messages.error(request, 'Данные отчета не найдены. Сначала выполните отчет')
            context = super(BaseReportView, self).get_context_data(**kwargs)
            context = self.get_default_context_data(**context)
            return self.render_to_response(context)

        filename = 'report_%s.xls' % utcnow().strftime('%Y%m%d_%H%M%S')

        workbook = xlwt.Workbook()
        worksheet = workbook.add_sheet('Отчет')

        self.write_xls_data(worksheet, context)

        response = HttpResponse(content_type='application/vnd.ms-excel')
        response['Content-Disposition'] = 'attachment; filename="%s"' % filename
        workbook.save(response)
        return response

    def write_xls_data(self, worksheet, context):
        self.styles = {
            'heading_style': xlwt.easyxf('font: bold 1, height 340'),
            'bottom_border_style': xlwt.easyxf('borders: bottom thin'),
            'left_center_style': xlwt.easyxf('align: vert centre, horiz left'),
            'right_center_style': xlwt.easyxf('align: wrap on, vert centre, horiz right'),
            'border_left_style': xlwt.easyxf(
                'borders: bottom thin, left thin, right thin, top thin;'
                'align: wrap on, vert centre, horiz left'
            ),
            'border_center_style': xlwt.easyxf(
                'borders: bottom thin, left thin, right thin, top thin;'
                'align: wrap on, vert centre, horiz centre'
            ),
            'border_right_style': xlwt.easyxf(
                'borders: bottom thin, left thin, right thin, top thin;'
                'align: wrap on, vert centre, horiz right'
            )
        }

        worksheet.write_merge(0, 0, 0, 3, self.report_name, style=self.styles['heading_style'])
        worksheet.row(0).height_mismatch = True
        worksheet.row(0).height = 500

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
