# -*- coding: utf-8 -*-
from django.conf import settings
from django.http import HttpResponseGone, HttpResponsePermanentRedirect, \
    HttpResponseRedirect, HttpResponseNotModified
from django.http.response import HttpResponseRedirectBase
from snippets.seo.enums import RedirectCodesEnum
from snippets.seo.router import router
from snippets.seo.models import SEOPage


class SEOMiddleware(object):
    """Middleware adds some template context variables"""
    @staticmethod
    def process_request(request):
        path = request.get_full_path()
        if not path.endswith('/') and settings.APPEND_SLASH:
            path += '/'
        redirect = router.get_path(path)
        if redirect is not None:
            http_code = int(redirect.http_code)
            if redirect.new_path == '' or http_code == RedirectCodesEnum.C410:
                return HttpResponseGone()
            elif http_code == RedirectCodesEnum.C301:
                return HttpResponsePermanentRedirect(redirect.new_path)
            elif http_code == RedirectCodesEnum.C302:
                return HttpResponseRedirect(redirect.new_path)
            elif http_code == RedirectCodesEnum.C304:
                return HttpResponseNotModified(redirect.new_path)
            response = HttpResponseRedirectBase(redirect.new_path)
            response.status_code = http_code
            return response

        try:
            full_path_parts = request.get_full_path().split('/')
            full_path_parts[1] = ''
            full_path = '/'.join(full_path_parts[1:])
            seo_page = SEOPage.objects.published().get(url__iexact=full_path)
            seo_page.apply_seo_params(request)

        except (SEOPage.DoesNotExist, SEOPage.MultipleObjectsReturned):
            pass

        return None
