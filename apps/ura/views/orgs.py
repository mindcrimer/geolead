# -*- coding: utf-8 -*-
from django.db.models import Q

from snippets.utils.datetime import utcnow
from ura.lib.resources import URAResource
from ura.lib.response import error_response, XMLResponse
from users.models import User


class URAOrgsResource(URAResource):
    """Получение списка организаций"""
    def post(self, request, *args, **kwargs):

        doc = request.data.xpath('/orgRequest')
        if len(doc) < 1:
            return error_response('Не найден объект orgRequest', code='orgRequest_not_found')

        doc = doc[0]
        doc_id = doc.get('idDoc', '')
        if not doc_id:
            return error_response('Не указан параметр idDoc', code='idDoc_not_found')

        orgs = User.objects\
            .filter(Q(pk=request.user.pk) | Q(supervisor=request.user)).filter(is_active=True)

        context = self.get_context_data(**kwargs)
        context.update({
            'doc_id': doc_id,
            'orgs': orgs,
            'create_date': utcnow()
        })

        return XMLResponse('ura/orgs.xml', context)
