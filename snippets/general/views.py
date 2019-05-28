from django.http import HttpResponseForbidden, HttpResponseBadRequest, HttpResponseNotFound, \
    HttpResponseServerError
from django.template.loader import render_to_string

from snippets.utils.i18n import get_language


def e400(request, exception, *args, **kwargs):
    """400 handler"""
    message = kwargs.get('message', '')
    request.LANGUAGE_CODE = get_language(request)
    return HttpResponseBadRequest(
        render_to_string(
            'errors/400.html', {
                'request_path': request.path,
                'message': message,
                'is_error_page': True
            },
            request=request,
            using='jinja2'
        )
    )


def e403(request, exception, *args, **kwargs):
    """403 handler"""
    message = kwargs.get('message', '')
    request.LANGUAGE_CODE = get_language(request)
    return HttpResponseForbidden(
        render_to_string(
            'errors/403.html', {
                'request_path': request.path,
                'message': message,
                'is_error_page': True
            },
            request=request,
            using='jinja2'
        )
    )


def e404(request, exception, *args, **kwargs):
    """404 handler"""
    message = kwargs.get('message', '')
    request.LANGUAGE_CODE = get_language(request)
    return HttpResponseNotFound(
        render_to_string(
            'errors/404.html', {
                'request_path': request.path,
                'message': message,
                'is_error_page': True
            },
            request=request,
            using='jinja2'
        )
    )


def e500(request, *args, **kwargs):
    """500 handler"""
    message = kwargs.get('message', '')
    request.LANGUAGE_CODE = get_language(request)
    return HttpResponseServerError(
        render_to_string(
            'errors/500.html', {
                'request_path': request.path,
                'message': message,
                'is_error_page': True
            },
            request=request,
            using='jinja2'
        )
    )
