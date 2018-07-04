from moving import service
from reports.utils import utc_to_local_time
from snippets.http.response import success_response
from snippets.utils.datetime import utcnow
from snippets.views import BaseView
from users.models import User
from wialon.auth import get_wialon_session_key, logout_session


class MovingTestView(BaseView):
    service_class = service.MovingService

    def get(self, request, **kwargs):
        now = utc_to_local_time(utcnow(), request.user.timezone)
        local_dt_from = now.replace(hour=0, minute=0, second=0)
        local_dt_to = now.replace(hour=23, minute=59, second=59)
        user = User.objects.get(pk=1)
        sess_id = get_wialon_session_key(user)
        moving_service = self.service_class(
            user=user,
            local_dt_from=local_dt_from,
            local_dt_to=local_dt_to,
            sess_id=sess_id
        )
        moving_service.exec_report()
        moving_service.analyze()
        logout_session(user, sess_id)

        return success_response()
