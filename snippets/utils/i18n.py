from django.utils.translation import get_language as django_get_language
from django.conf import settings


def get_language(request):
    if hasattr(request, 'LANGUAGE_CODE'):
        return request.LANGUAGE_CODE

    return django_get_language()[:2] or settings.DEFAULT_LANGUAGE
