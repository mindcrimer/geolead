# -*- coding: utf-8 -*-
from django.conf.urls import url

from ura import views


urlpatterns = (
    url(
        r'^jobs/$',
        views.URAJobsView.as_view(), name='ura_jobs'
    ),
)
