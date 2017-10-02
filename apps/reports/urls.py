# -*- coding: utf-8 -*-
from django.conf.urls import url

from reports.views.discharge import DischargeView
from reports.views.drivingstyle import DrivingStyleView

urlpatterns = (
    url(
        r'^discharge/$',
        DischargeView.as_view(), name='discharge'
    ),
    url(
        r'^driving-style/$',
        DrivingStyleView.as_view(), name='driving_style'
    )
)
