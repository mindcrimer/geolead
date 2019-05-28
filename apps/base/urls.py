from django.urls import path

from base import views


app_name = 'base'

urlpatterns = (
    path(
        '400/',
        views.Error400View.as_view(), name='400'
    ),
    path(
        '403/',
        views.Error403View.as_view(), name='403'
    ),
    path(
        '404/',
        views.Error404View.as_view(), name='404'
    ),
    path(
        '500/',
        views.Error500View.as_view(), name='500'
    ),
    path(
        '500-test/',
        views.Error500TestView.as_view(), name='500_test'
    )
)
