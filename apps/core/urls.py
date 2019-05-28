from django.urls import path

from core import views


app_name = 'core'

urlpatterns = (
    path(
        '',
        views.ReportsHomeView.as_view(), name='reports_home'
    ),
    path(
        'reports/nlmk/',
        views.ReportsHomeView.as_view(), name='reports_nlmk_home'
    ),
    path(
        'nlmk/',
        views.ReportsHomeView.as_view(), name='reports_nlmk_home_short'
    ),
    path(
        'reports/vchm/',
        views.ReportsVchmHomeView.as_view(), name='reports_vchm_home'
    ),
    path(
        'vchm/',
        views.ReportsVchmHomeView.as_view(), name='reports_vchm_home_short'
    ),
    path(
        'exit/',
        views.ExitView.as_view(), name='exit'
    )
)
