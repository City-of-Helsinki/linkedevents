from django.contrib.auth import get_user_model
from rest_framework import serializers


class UserSerializer(serializers.ModelSerializer):
    display_name = serializers.ReadOnlyField(source="get_display_name")

    def to_representation(self, obj):
        rep = super().to_representation(obj)
        default_org = obj.get_default_organization()
        if default_org:
            rep["organization"] = default_org.id
        rep["admin_organizations"] = [org.id for org in obj.admin_organizations.all()]
        rep["registration_admin_organizations"] = [
            org.id for org in obj.registration_admin_organizations.all()
        ]
        rep["organization_memberships"] = [
            org.id for org in obj.organization_memberships.all()
        ]
        return rep

    class Meta:
        fields = [
            "last_login",
            "username",
            "email",
            "date_joined",
            "first_name",
            "last_name",
            "uuid",
            "department_name",
            "is_staff",
            "display_name",
            "is_external",
        ]
        model = get_user_model()
