from django.conf.urls import url

from reports.views.discharge import DischargeView
from reports.views.drivingstyle import DrivingStyleView
from reports.views.finished_jobs import FinishedJobsView
from reports.views.invalid_job_start_end import InvalidJobStartEndView
from reports.views.faults import FaultsView
from reports.views.overstatements import OverstatementsView
from reports.views.vchm_driving_style import VchmDrivingStyleView
from reports.views.vchm_idle_times import VchmIdleTimesView
from reports.views.vchm_taxiing import VchmTaxiingView

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
        r'^faults/$',
        FaultsView.as_view(), name='faults'
    ),
    url(
        r'^overstatements/$',
        OverstatementsView.as_view(), name='overstatements'
    ),
    url(
        r'^vchm/driving_style/$',
        VchmDrivingStyleView.as_view(), name='vchm_driving_style'
    ),
    url(
        r'^vchm/idle_times/$',
        VchmIdleTimesView.as_view(), name='vchm_idle_times'
    ),
    url(
        r'^vchm/taxiing/$',
        VchmTaxiingView.as_view(), name='vchm_taxiing'
    )
)
