from django.core.exceptions import ValidationError


class BaseAPIError(Exception):
    """Базовый класс ошибки REST API"""
    def __init__(self, message, *args, **kwargs):
        code = kwargs.pop('code', None)
        super(BaseAPIError, self).__init__(message, *args, **kwargs)
        self.code = code


class APIParseError(BaseAPIError):
    """Ошибка при невозможности спарсить запрос"""
    pass


class APIValidationError(ValidationError, BaseAPIError):
    """Ошибка для валидации входных параметров API"""
    pass


class APISourceEndError(ValidationError, BaseAPIError):
    """Ошибка при выполнении запросов получения данных из источника данных"""
    pass


class APIProcessError(BaseAPIError):
    """Ошибка выполнения функций API"""
    def __init__(self, message, *args, **kwargs):
        http_status = kwargs.pop('http_status', None)
        super(APIProcessError, self).__init__(message, *args, **kwargs)
        self.http_status = http_status


class AuthenticationFailed(BaseAPIError):
    """Ошибка при авторизации"""
    pass


class ReportException(Exception):
    pass
