# -*- coding: utf-8 -*-
from django.views import View
from django.views.generic import TemplateView


class BaseTemplateView(TemplateView):
    """Базовый класс для представлений c шаблоном"""
    template_name = None
    template_engine = 'jinja2'
    content_type = 'text/html'

    def get_page(self, param='page'):
        """Получает номер страницы пагинации"""
        page = self.kwargs.get(param)
        try:
            page = int(page)
        except (ValueError, TypeError):
            page = 1

        if page < 1:
            page = 1

        return page


class BaseView(View):
    """Базовый класс для представлений"""
    pass
