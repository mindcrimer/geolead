from base.exceptions import APIProcessError
from snippets.utils.datetime import utcnow
from ura.lib.resources import URAResource
from ura.lib.response import XMLResponse, error_response
from wialon.api import get_points
from wialon.auth import get_wialon_session_key, logout_session


class URAPointsResource(URAResource):
    """Список геозон (точек)"""
    def post(self, request, *args, **kwargs):

        doc = request.data.xpath('/pointsRequest')
        if len(doc) < 1:
            return error_response(
                'Не найден объект pointsRequest', code='pointsRequest_not_found'
            )

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
            points = get_points(request.user)
        except APIProcessError as e:
            return error_response(str(e), code=e.code)
        finally:
            logout_session(request.user, sess_id)

        context = self.get_context_data(**kwargs)
        context.update({
            'doc_id': doc_id,
            'create_date': utcnow(),
            'points': points,
            'org_id': org_id
        })

        return XMLResponse('ura/points.xml', context)
