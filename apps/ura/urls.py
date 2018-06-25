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
        r'^jobs/set/$',
        views.URASetJobsResource.as_view(),
        name='ura_jobs_set'
    ),
    url(
        r'^jobs/break/$',
        views.URABreakJobsResource.as_view(),
        name='ura_jobs_break'
    ),
    url(
        r'^races/$',
        views.URARacesResource.as_view(),
        name='ura_races'
    ),
    url(
        r'^moving/$',
        views.URAMovingResource.as_view(),
        name='ura_moving'
    ),
    url(
        r'^orgs/$',
        views.URAOrgsResource.as_view(),
        name='ura_orgs'
    ),
    url(
        r'^points/$',
        views.URAPointsResource.as_view(),
        name='ura_points'
    ),
    url(
        r'^routes/$',
        views.URARoutesResource.as_view(),
        name='ura_routes'
    ),
    url(
        r'^units/$',
        views.URAUnitsResource.as_view(),
        name='ura_units'
    )
)
