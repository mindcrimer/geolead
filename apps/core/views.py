# -*- coding: utf-8 -*-
from snippets.views import BaseTemplateView


class HomeView(BaseTemplateView):
    """Главная страница"""
    template_name = 'core/home.html'
