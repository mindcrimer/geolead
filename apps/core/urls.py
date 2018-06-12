# -*- coding: utf-8 -*-
from django.conf.urls import url

from core import views


urlpatterns = (
    url(
        r'^$',
        views.ReportsHomeView.as_view(), name='reports_home'
    ),
    url(
        r'^reports/nlmk/$',
        views.ReportsHomeView.as_view(), name='reports_nlmk_home'
    ),
    url(
        r'^nlmk/$',
        views.ReportsHomeView.as_view(), name='reports_nlmk_home_short'
    ),
    url(
        r'^reports/vchm/$',
        views.ReportsVchmHomeView.as_view(), name='reports_vchm_home'
    ),
    url(
        r'^vchm/$',
        views.ReportsVchmHomeView.as_view(), name='reports_vchm_home_short'
    ),
    url(
        r'^exit/$',
        views.ExitView.as_view(), name='exit'
    ),
)
