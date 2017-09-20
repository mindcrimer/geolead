# -*- coding: utf-8 -*-
from django.conf.urls import url

from reports import views


urlpatterns = (
    url(
        r'^over-spanding/$',
        views.OverSpandingView.as_view(), name='over_spanding'
    ),
    url(
        r'^driving-style/$',
        views.DrivingStyleView.as_view(), name='driving_style'
    )
)
