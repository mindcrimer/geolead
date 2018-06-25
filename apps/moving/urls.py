from django.conf.urls import url

from moving import views


urlpatterns = (
    url(
        r'^test/$',
        views.MovingTestView.as_view(), name='moving_test'
    ),
)
