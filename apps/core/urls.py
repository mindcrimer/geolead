# -*- coding: utf-8 -*-
from django.conf.urls import url

from core import views


urlpatterns = (
    url(
        r'^$',
        views.ReportsHomeView.as_view(), name='reports_nlmk_home'
    ),
    url(
        r'^reports/vchm/$',
        views.ReportsVchmHomeView.as_view(), name='reports_vchm_home'
    ),
    url(
        r'^exit/$',
        views.ExitView.as_view(), name='exit'
    ),
)
