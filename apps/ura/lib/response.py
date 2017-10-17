from django.template.response import SimpleTemplateResponse


BASIC_ERROR_TEMPLATE = 'ura/errors/error.xml'


class XMLResponse(SimpleTemplateResponse):
    def __init__(self, template=None, context=None, content_type=None, status=None, charset=None,
                 using=None):
        content_type = content_type if content_type else 'application/xml'
        template = template if template else BASIC_ERROR_TEMPLATE
        charset = charset if charset else 'utf-8'
        using = using if using else 'jinja2'

        super(XMLResponse, self).__init__(
            template, context=context, content_type=content_type, status=status,
            charset=charset, using=using
        )


def error_response(message=None, status=400, code=None):
    result = {
        'message': message,
        'code': code if code else 'error'
    }

    return XMLResponse(context=result, status=status)


def success_response(message=None, status=200):
    result = {
        'status': 'ok'
    }

    if message is not None:
        result['detail'] = {
            'message': message
        }
    return XMLResponse(context=result, status=status)


def validation_error_response(errors, status=400, code=None):
    errors_list = []
    for name, v in errors.items():
        errors_list.extend([str('; '.join(e.messages)) for e in v.data])

    return error_response(', '.join(errors_list), status=status, code=code)
