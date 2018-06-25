from django.conf.urls import url

from base import views


urlpatterns = (
    url(
        r'^400/$',
        views.Error400View.as_view(), name='400'
    ),
    url(
        r'^403/$',
        views.Error403View.as_view(), name='403'
    ),
    url(
        r'^404/$',
        views.Error404View.as_view(), name='404'
    ),
    url(
        r'^500/$',
        views.Error500View.as_view(), name='500'
    ),
    url(
        r'^500-test/$',
        views.Error500TestView.as_view(), name='500_test'
    )
)
