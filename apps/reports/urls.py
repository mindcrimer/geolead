# -*- coding: utf-8 -*-
from django.conf.urls import url

from reports import views


urlpatterns = (
    url(
        r'^discharge/$',
        views.DischargeView.as_view(), name='discharge'
    ),
    url(
        r'^driving-style/$',
        views.DrivingStyleView.as_view(), name='driving_style'
    )
)
