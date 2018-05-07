from snippets.template_backends.jinja2 import jinjaglobal


@jinjaglobal
def get_session_user(request):
    return request.session.get('user', '')


@jinjaglobal
def get_session_sid(request):
    return request.session.get('sid', '')
