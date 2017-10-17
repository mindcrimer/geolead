# -*- coding: utf-8 -*-
from base.exceptions import APIProcessError
from snippets.utils.datetime import utcnow
from ura.lib.resources import URAResource
from ura.lib.response import XMLResponse, error_response
from ura.utils import get_organization_user
from ura.wialon.api import get_drivers_list


class URADriversResource(URAResource):
    """Список водителей"""
    def post(self, request, *args, **kwargs):

        doc = request.data.xpath('/driversRequest')
        if len(doc) < 1:
            return error_response(
                'Не найден объект driversRequest', code='driversRequest_not_found'
            )

        doc = doc[0]
        doc_id = doc.get('idDoc', '')
        if not doc_id:
            return error_response('Не указан параметр idDoc', code='idDoc_not_found')

        try:
            org_id = int(doc.get('idOrg', ''))
        except ValueError:
            org_id = 0

        user = get_organization_user(request, org_id)

        try:
            drivers = get_drivers_list(user)
        except APIProcessError as e:
            return error_response(str(e), code=e.code)

        context = self.get_context_data(**kwargs)
        context.update({
            'doc_id': doc_id,
            'create_date': utcnow(),
            'drivers': drivers,
            'org_id': org_id
        })

        return XMLResponse('ura/drivers.xml', context)
