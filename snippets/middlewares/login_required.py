# -*- coding: utf-8 -*-
import re

from django.conf import settings
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.http import HttpResponseRedirect
from django.template.defaultfilters import urlencode


EXEMPT_URLS = ()
if settings.LOGIN_URL:
    EXEMPT_URLS = (re.compile(settings.LOGIN_URL.lstrip('/')),)

if hasattr(settings, 'LOGIN_EXEMPT_URLS'):
    EXEMPT_URLS += tuple(
        re.compile(expr) for expr in settings.LOGIN_EXEMPT_URLS
    )


class LoginRequiredMiddleware(object):
    """
    Middleware that requires a user to be authenticated to view any page other
    than LOGIN_URL. Exemptions to this requirement can optionally be specified
    in settings via a list of regular expressions in LOGIN_EXEMPT_URLS (which
    you can copy from your urls.py).

    Requires authentication middleware and template context processors to be
    loaded. You'll get an error if they aren't.
    """
    @staticmethod
    def process_request(request):
        if not getattr(settings, 'LOGIN_ALWAYS_REQUIRED', True):
            return None

        if not request.user.is_authenticated():
            path = request.path_info.lstrip('/')

            if not any(m.match(path) for m in EXEMPT_URLS):
                next_url = ''

                if getattr(settings, 'LOGIN_CONTINUE', False) \
                        and len(request.path) > 1:
                    next_url = '?%s=%s' % (REDIRECT_FIELD_NAME, urlencode(request.get_full_path()))
                return HttpResponseRedirect(
                    '%s%s' % (settings.LOGIN_URL, next_url)
                )
