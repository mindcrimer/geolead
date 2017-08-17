from functools import wraps

from django.http import HttpResponse
from django.http.response import HttpResponseRedirectBase

from snippets.slimmer import slimmer


def compress_html(view_func):
    """
    Decorator that adds headers to a response so that it will
    never be cached.
    """
    def _wrapped_view_func(request, *args, **kwargs):
        response = view_func(request, *args, **kwargs)
        if isinstance(response, HttpResponse) \
                and not isinstance(response, HttpResponseRedirectBase) \
                and response.get('Content-Type', None).find('text/html') == 0:
            response.content = slimmer.xhtml_slimmer(response.content)
        return response
    return wraps(view_func)(_wrapped_view_func)
