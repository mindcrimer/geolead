# -*- coding: utf-8 -*-
from django.conf.urls import url

from snippets.seo import views

urlpatterns = (
    url(r'^sitemap.xml$', views.SitemapView.as_view(), name='sitemap'),
    url(r'^robots.txt$', views.RobotsView.as_view(), name='robots'),
)
