# -*- coding: utf-8 -*-
from django.conf import settings

from snippets.seo.models import Robot
from snippets.seo.utils import collect_sitemap_urls
from snippets.views import BaseTemplateView


class SitemapView(BaseTemplateView):
    """sitemap.xml"""
    template_name = 'seo/sitemap.xml'
    content_type = 'application/xml'

    def get_context_data(self, **kwargs):
        context = super(SitemapView, self).get_context_data(**kwargs)

        context.update({
            'urls': collect_sitemap_urls(),
            'site_url': settings.SITE_URL
        })
        return context


class RobotsView(BaseTemplateView):
    """robots.txt"""
    template_name = 'seo/robots.txt'
    content_type = 'text/plain'

    def get_context_data(self, **kwargs):
        context = super(RobotsView, self).get_context_data(**kwargs)
        user_agents = Robot.objects.published().order_by('ordering')

        context.update({
            'user_agents': user_agents,
            'site_url': settings.SITE_URL
        })
        return context
