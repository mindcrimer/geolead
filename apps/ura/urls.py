# -*- coding: utf-8 -*-
from django.conf.urls import url

from ura import views


urlpatterns = (
    url(
        r'^drivers/$',
        views.URADriversResource.as_view(),
        name='ura_drivers'
    ),
    url(
        r'^echo/$',
        views.URAEchoResource.as_view(),
        name='ura_echo'
    ),
    url(
        r'^jobs/$',
        views.URAJobsResource.as_view(),
        name='ura_jobs'
    ),
    url(
        r'^orgs/$',
        views.URAOrgsResource.as_view(),
        name='ura_orgs'
    )
)
