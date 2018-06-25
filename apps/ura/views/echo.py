from snippets.utils.datetime import utcnow
from ura.lib.resources import URAResource
from ura.lib.response import error_response, XMLResponse


class URAEchoResource(URAResource):
    """Тест работоспособности сервиса"""
    def post(self, request, *args, **kwargs):

        doc = request.data.xpath('/echoRequest')
        if len(doc) < 1:
            return error_response('Не найден объект echoRequest', code='echoRequest_not_found')

        doc = doc[0]
        doc_id = doc.get('idDoc', '')
        if not doc_id:
            return error_response('Не указан параметр idDoc', code='idDoc_not_found')

        context = self.get_context_data(**kwargs)
        context.update({
            'doc_id': doc_id,
            'create_date': utcnow()
        })
        return XMLResponse('ura/echo.xml', context)
