from django.contrib.auth import get_user_model
from rest_framework import generics, permissions, viewsets

from audit_log.mixins import AuditLogApiViewMixin
from helevents.serializers import UserSerializer
from linkedevents.registry import register_view


class UserViewSet(AuditLogApiViewMixin, viewsets.ReadOnlyModelViewSet):
    queryset = get_user_model().objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return self.queryset
        else:
            # id is used because pk seems to give a string for ApiKeyUser
            return self.queryset.filter(pk=user.id)

    def get_object(self, skip_log_ids=False):
        username = self.kwargs.get("username", None)
        if username:
            qs = self.get_queryset()
            obj = generics.get_object_or_404(qs, username=username)
        else:
            obj = self.request.user

        self.check_object_permissions(self.request, obj)
        self._add_audit_logged_object_ids(obj)

        return obj


register_view(UserViewSet, "user")
