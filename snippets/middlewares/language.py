# -*- coding: utf-8 -*-
from django.conf import settings
from django.http.response import Http404
from django.utils import translation
from django.utils.translation import ugettext_lazy as _


class LanguageMiddleware(object):
    """Language middleware"""
    @staticmethod
    def process_request(request):
        full_path_parts = request.get_full_path().split('/')
        request_lang = None

        if len(full_path_parts) > 2 and len(full_path_parts[1]) == 2:
            request_lang = full_path_parts[1]

        lang = (
            request_lang
            or translation.get_language_from_request(request, check_path=False)
            or settings.DEFAULT_LANGUAGE
        ).lower()

        available_langs = settings.LANGUAGE_CODES_PUBLIC
        if lang not in available_langs:
            raise Http404(_('Язык "%s" не зарегистрирован в системе') % lang)

        translation.activate(lang)
        request.LANGUAGE_CODE = lang
        request.session[settings.LANGUAGE_COOKIE_NAME] = lang
        return None

    @staticmethod
    def process_response(request, response):
        lang = getattr(request, 'LANGUAGE_CODE', None) \
               or request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME)\
               or settings.DEFAULT_LANGUAGE

        if not request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME) \
                or (lang and lang != request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME)):
            response.set_cookie(settings.LANGUAGE_COOKIE_NAME, lang, max_age=1000)
        return response
