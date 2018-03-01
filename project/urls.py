# -*- coding: utf-8 -*-
from django.conf import settings
from django.conf.urls import include, url
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.views.static import serve

admin.autodiscover()

handler400 = 'snippets.general.views.e400'
handler403 = 'snippets.general.views.e403'
handler404 = 'snippets.general.views.e404'
handler500 = 'snippets.general.views.e500'

urlpatterns = (
    url(r'^ckeditor/', include('ckeditor_uploader.urls')),
    url(r'^admin/', include(admin.site.urls)),
    url(r'^ura/', include('ura.urls', namespace='ura')),
    url(r'^', include('reports.urls', namespace='reports')),
    url(r'^', include('base.urls', namespace='base')),
    # url(r'^', include('snippets.seo.urls', namespace='seo')),
)

if settings.DEBUG is True:
    urlpatterns += (
        url(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
    )

if getattr(settings, 'ENV', 'production') == 'dev':
    urlpatterns += tuple(staticfiles_urlpatterns())

urlpatterns += (
    url(r'^', include('core.urls', namespace='core')),
)
