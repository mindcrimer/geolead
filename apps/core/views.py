# -*- coding: utf-8 -*-
from snippets.views import BaseTemplateView


class HomeView(BaseTemplateView):
    """Главная страница"""
    template_name = 'core/home.html'

    def get_context_data(self, **kwargs):
        kwargs = super(HomeView, self).get_context_data(**kwargs)
        kwargs['sid'] = self.request.GET.get('sid', None)
        kwargs['user'] = self.request.GET.get('user', None)
        return kwargs
