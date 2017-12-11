# -*- coding: utf-8 -*-
from django.conf.urls import url

from reports.views.discharge import DischargeView
from reports.views.drivingstyle import DrivingStyleView
from reports.views.finished_jobs import FinishedJobsView
from reports.views.invalid_job_start_end import InvalidJobStartEndView
from reports.views.malfunctions import MalfunctionsView
from reports.views.overstatements import OverstatementsView


urlpatterns = (
    url(
        r'^discharge/$',
        DischargeView.as_view(), name='discharge'
    ),
    url(
        r'^driving-style/$',
        DrivingStyleView.as_view(), name='driving_style'
    ),
    url(
        r'^finished-jobs/$',
        FinishedJobsView.as_view(), name='finished_jobs'
    ),
    url(
        r'^invalid-job-start-end/$',
        InvalidJobStartEndView.as_view(), name='invalid_job_start_end'
    ),
    url(
        r'^malfunctions/$',
        MalfunctionsView.as_view(), name='malfunctions'
    ),
    url(
        r'^overstatements/$',
        OverstatementsView.as_view(), name='overstatements'
    )
)
