# -*- coding: utf-8 -*-
from django.conf.urls import url

from core import views


urlpatterns = (
    url(
        r'^$',
        views.HomeView.as_view(), name='home'
    ),
    url(
        r'^over-spanding/$',
        views.OverSpandingView.as_view(), name='over_spanding'
    )
)
