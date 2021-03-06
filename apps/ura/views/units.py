from base.exceptions import APIProcessError
from snippets.utils.datetime import utcnow
from ura.lib.resources import URAResource
from ura.lib.response import error_response, XMLResponse
from wialon.api import get_units
from wialon.auth import get_wialon_session_key, logout_session


class URAUnitsResource(URAResource):
    """Список элементов"""
    def post(self, request, *args, **kwargs):

        doc = request.data.xpath('/unitsRequest')
        if len(doc) < 1:
            return error_response('Не найден объект unitsRequest', code='unitsRequest_not_found')

        doc = doc[0]
        doc_id = doc.get('idDoc', '')
        if not doc_id:
            return error_response('Не указан параметр idDoc', code='idDoc_not_found')

        try:
            org_id = int(doc.get('idOrg', ''))
        except ValueError:
            org_id = 0

        sess_id = get_wialon_session_key(request.user)
        try:
            units = get_units(sess_id)
        except APIProcessError as e:
            return error_response(str(e), code=e.code)
        finally:
            logout_session(request.user, sess_id)

        context = self.get_context_data(**kwargs)
        context.update({
            'doc_id': doc_id,
            'create_date': utcnow(),
            'units': units,
            'org_id': org_id
        })

        return XMLResponse('ura/units.xml', context)
