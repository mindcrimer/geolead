from django.template.response import TemplateResponse

from snippets.views import BaseTemplateView, BaseView


class TemplateResponse400(TemplateResponse):
    status_code = 400


class TemplateResponse403(TemplateResponse):
    status_code = 403


class TemplateResponse404(TemplateResponse):
    status_code = 404


class TemplateResponse500(TemplateResponse):
    status_code = 500


class BaseErrorView(BaseTemplateView):
    def get_context_data(self, **kwargs):
        kwargs = super(BaseErrorView, self).get_context_data(**kwargs)
        message = kwargs.get('message', '')
        request = kwargs.get('view').request

        kwargs.update(
            request_path=request.path,
            message=message,
            is_error_page=True
        )
        return kwargs


class Error400View(BaseErrorView):
    """Неправильный запрос"""
    response_class = TemplateResponse400
    template_name = 'errors/400.html'


class Error403View(BaseErrorView):
    """Доступ запрещен"""
    response_class = TemplateResponse403
    template_name = 'errors/403.html'


class Error404View(BaseErrorView):
    """Страница не найдена"""
    response_class = TemplateResponse404
    template_name = 'errors/404.html'


class Error500View(BaseErrorView):
    """Внутренняя ошибка сервера"""
    response_class = TemplateResponse500
    template_name = 'errors/500.html'


class Error500TestView(BaseView):
    """Внутренняя ошибка сервера"""
    def get(self, request, **kwargs):
        raise ValueError('Test 500 error')
