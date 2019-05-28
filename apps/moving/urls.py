from django.urls import path

from moving import views


app_name = 'moving'

urlpatterns = (
    path(
        'test/',
        views.MovingTestView.as_view(), name='moving_test'
    ),
)
