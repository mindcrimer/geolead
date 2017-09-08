# -*- coding: utf-8 -*-
from django.http import JsonResponse, HttpResponse


class Response(JsonResponse):
    pass


class XMLResponse(HttpResponse):
    def __init__(self, data, **kwargs):
        kwargs.setdefault('content_type', 'application/xml')
        super(XMLResponse, self).__init__(content=data, **kwargs)



def error_response(message=None, status=400, code=None):
    result = {
        'status': 'error'
    }
    if message is not None:
        result['detail'] = message

    if code:
        result['code'] = code
    return Response(result, status=status)


def success_response(message=None, status=200):
    result = {
        'status': 'ok'
    }
    if message is not None:
        result['detail'] = message
    return Response(result, status=status)


def validation_error_response(errors, status=400, code=None):
    return error_response(message={'errors': errors}, status=status, code=code)


def form_validation_error_response(errors, status=400, code=None):
    return error_response(message={'errors': errors}, status=status, code=code)
