from django.urls import path

from ura import views


app_name = 'ura'


urlpatterns = (
    path(
        'drivers/',
        views.URADriversResource.as_view(),
        name='ura_drivers'
    ),
    path(
        'echo/',
        views.URAEchoResource.as_view(),
        name='ura_echo'
    ),
    path(
        'jobs/set/',
        views.URASetJobsResource.as_view(),
        name='ura_jobs_set'
    ),
    path(
        'jobs/break/',
        views.URABreakJobsResource.as_view(),
        name='ura_jobs_break'
    ),
    path(
        'races/',
        views.URARacesResource.as_view(),
        name='ura_races'
    ),
    path(
        'moving/',
        views.URAMovingResource.as_view(),
        name='ura_moving'
    ),
    path(
        'orgs/',
        views.URAOrgsResource.as_view(),
        name='ura_orgs'
    ),
    path(
        'points/',
        views.URAPointsResource.as_view(),
        name='ura_points'
    ),
    path(
        'routes/',
        views.URARoutesResource.as_view(),
        name='ura_routes'
    ),
    path(
        'units/',
        views.URAUnitsResource.as_view(),
        name='ura_units'
    )
)
