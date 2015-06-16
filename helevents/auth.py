from django.utils.translation import ugettext as _
from django.contrib.auth import get_user_model
from rest_framework_jwt.authentication import JSONWebTokenAuthentication
from rest_framework import exceptions


class JWTAuthentication(JSONWebTokenAuthentication):

    def populate_user(self, user, data):
        exclude_fields = ['is_staff', 'password', 'is_superuser']
        user_fields = [f.name for f in user._meta.fields if f not in exclude_fields]
        changed = False
        for field in user_fields:
            if field in data:
                val = data[field]
                if getattr(user, field) != val:
                    setattr(user, field, val)
                    changed = True
        return changed

    def authenticate_credentials(self, payload):
        User = get_user_model()
        user_id = payload.get('sub')
        if not user_id:
            msg = _('Invalid payload.')
            raise exceptions.AuthenticationFailed(msg)

        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            user = User(pk=user_id)
            user.set_unusable_password()

        changed = self.populate_user(user, payload)
        if changed:
            user.save()

        return super(JWTAuthentication, self).authenticate_credentials(payload)
