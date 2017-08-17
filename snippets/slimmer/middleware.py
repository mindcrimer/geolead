from django.http import HttpResponse

from snippets.slimmer import slimmer


class CompressHtmlMiddleware(object):
    @staticmethod
    def process_response(request, response):
        if isinstance(response, HttpResponse) and \
                response.get('Content-Type', None).find('text/html;') == 0:
            response.content = slimmer.xhtml_slimmer(response.content)
        return response
