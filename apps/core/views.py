# -*- coding: utf-8 -*-
from django.urls import reverse

from django.http import HttpResponseRedirect
from snippets.views import BaseTemplateView, BaseView


class HomeView(BaseTemplateView):
    """Главная страница"""
    template_name = 'core/home.html'

    def get(self, request, **kwargs):
        sid = self.request.GET.get('sid', None)
        if sid:
            request.session['sid'] = sid

        user = self.request.GET.get('user', None)
        if user:
            request.session['user'] = user

        if user or sid:
            request.session.set_expiry(60 * 60)

        kwargs['sid'] = request.session.get('sid')
        kwargs['user'] = request.session.get('user')

        return super(HomeView, self).get(request, **kwargs)


class ExitView(BaseView):
    def get(self, request, **kwargs):
        request.session.flush()
        return HttpResponseRedirect(reverse('core:home'))
