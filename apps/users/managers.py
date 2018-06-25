from django.contrib.auth.models import UserManager as DjangoUserManager
from django.utils import timezone


class UserManager(DjangoUserManager):
    def _create_user(self, username, email, password, **extra_fields):

        now = timezone.now()
        if not username:
            raise ValueError('The given username must be set')

        email = self.normalize_email(email)
        user = self.model(
            username=username,
            email=email,
            is_active=True,
            last_login=now,
            date_joined=now,
            **extra_fields
        )

        if password:
            user.set_password(password)

        user.save(using=self._db)

        return user
