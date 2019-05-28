from django.urls import path

from reports.views.discharge import DischargeView
from reports.views.drivingstyle import DrivingStyleView
from reports.views.finished_jobs import FinishedJobsView
from reports.views.invalid_job_start_end import InvalidJobStartEndView
from reports.views.faults import FaultsView
from reports.views.overstatements import OverstatementsView
from reports.views.vchm_driving_style import VchmDrivingStyleView
from reports.views.vchm_idle_times import VchmIdleTimesView
from reports.views.vchm_taxiing import VchmTaxiingView


app_name = 'reports'

urlpatterns = (
    path(
        'discharge/',
        DischargeView.as_view(), name='discharge'
    ),
    path(
        'driving-style/',
        DrivingStyleView.as_view(), name='driving_style'
    ),
    path(
        'finished-jobs/',
        FinishedJobsView.as_view(), name='finished_jobs'
    ),
    path(
        'invalid-job-start-end/',
        InvalidJobStartEndView.as_view(), name='invalid_job_start_end'
    ),
    path(
        'faults/',
        FaultsView.as_view(), name='faults'
    ),
    path(
        'overstatements/',
        OverstatementsView.as_view(), name='overstatements'
    ),
    path(
        'vchm/driving_style/',
        VchmDrivingStyleView.as_view(), name='vchm_driving_style'
    ),
    path(
        'vchm/idle_times/',
        VchmIdleTimesView.as_view(), name='vchm_idle_times'
    ),
    path(
        'vchm/taxiing/',
        VchmTaxiingView.as_view(), name='vchm_taxiing'
    )
)
