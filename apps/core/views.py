# -*- coding: utf-8 -*-
from django.urls import reverse
from django.http import HttpResponseRedirect

from snippets.views import BaseTemplateView, BaseView


class BaseReportsHomeView(BaseTemplateView):
    template_name = 'core/reports_nlmk_home.html'

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

        return super(BaseReportsHomeView, self).get(request, **kwargs)


class ReportsHomeView(BaseReportsHomeView):
    """Главная страница отчетов НЛМК"""
    template_name = 'core/reports_nlmk_home.html'

    def get(self, request, **kwargs):
        request.session['scope'] = 'nlmk'
        return super(ReportsHomeView, self).get(request, **kwargs)


class ReportsVchmHomeView(BaseReportsHomeView):
    """Главная страница отчетов ВЧМ"""
    template_name = 'core/reports_vchm_home.html'

    def get(self, request, **kwargs):
        request.session['scope'] = 'vchm'
        return super(ReportsVchmHomeView, self).get(request, **kwargs)


class ExitView(BaseView):
    def get(self, request, **kwargs):
        request.session.flush()
        scope = request.session.get('scope', 'nlmk')
        view_name = 'reports_%s_home' % scope
        return HttpResponseRedirect(reverse('core:%s' % view_name))
