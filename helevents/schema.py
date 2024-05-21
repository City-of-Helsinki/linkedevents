from drf_spectacular.extensions import OpenApiSerializerExtension

from helevents.serializers import UserSerializer


class UserSerializerExtension(OpenApiSerializerExtension):
    target_class = UserSerializer

    def map_serializer(self, auto_schema, direction):
        result = super().map_serializer(auto_schema, direction)

        result["required"].extend(["is_staff", "is_superuser"])

        return result
