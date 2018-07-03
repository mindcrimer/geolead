from moving import service
from reports.utils import utc_to_local_time
from snippets.http.response import  success_response
from snippets.utils.datetime import utcnow
from snippets.views import BaseView
from users.models import User


class MovingTestView(BaseView):
    service_class = service.MovingService

    def get(self, request, **kwargs):
        now = utc_to_local_time(utcnow(), request.user.timezone)
        local_dt_from = now.replace(hour=0, minute=0, second=0)
        local_dt_to = now.replace(hour=23, minute=59, second=59)
        user = User.objects.get(pk=1)
        moving_service = self.service_class(
            user=user,
            local_dt_from=local_dt_from,
            local_dt_to=local_dt_to
        )
        moving_service.exec_report()
        return success_response()
