from django.conf import settings
from django.urls import re_path, include, path
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.views.static import serve


admin.autodiscover()

handler400 = 'snippets.general.views.e400'
handler403 = 'snippets.general.views.e403'
handler404 = 'snippets.general.views.e404'
handler500 = 'snippets.general.views.e500'

urlpatterns = (
    re_path(r'^ckeditor/', include('ckeditor_uploader.urls')),
    path('admin/', admin.site.urls),
    path('ura/', include('ura.urls', namespace='ura')),
    path('moving/', include('moving.urls', namespace='moving')),
    path('', include('reports.urls', namespace='reports')),
    path('', include('base.urls', namespace='base'))
)

if settings.DEBUG is True:
    urlpatterns += (
        re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
    )

if getattr(settings, 'ENV', 'production') == 'dev':
    urlpatterns += tuple(staticfiles_urlpatterns())

urlpatterns += (
    path('', include('core.urls', namespace='core')),
)
