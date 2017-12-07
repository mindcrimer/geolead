# -*- coding: utf-8 -*-
from base.exceptions import APIProcessError
from snippets.utils.datetime import utcnow
from ura.lib.resources import URAResource
from ura.lib.response import error_response, XMLResponse
from wialon.api import get_routes


class URARoutesResource(URAResource):
    """Список маршрутов"""
    def post(self, request, *args, **kwargs):

        doc = request.data.xpath('/routesRequest')
        if len(doc) < 1:
            return error_response('Не найден объект routesRequest', code='routesRequest_not_found')

        doc = doc[0]
        doc_id = doc.get('idDoc', '')
        if not doc_id:
            return error_response('Не указан параметр idDoc', code='idDoc_not_found')

        try:
            org_id = int(doc.get('idOrg', ''))
        except ValueError:
            org_id = 0

        try:
            routes = get_routes(request.user)
        except APIProcessError as e:
            return error_response(str(e), code=e.code)

        context = self.get_context_data(**kwargs)
        context.update({
            'doc_id': doc_id,
            'create_date': utcnow(),
            'routes': routes,
            'org_id': org_id
        })

        return XMLResponse('ura/routes.xml', context)
