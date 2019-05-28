from django.http import JsonResponse


class Response(JsonResponse):
    pass


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
