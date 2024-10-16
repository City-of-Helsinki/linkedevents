import importlib
import urllib.parse

from django.utils.translation import gettext_lazy as _
from rest_framework import relations, serializers

from events.models import Event, Image, Keyword, Place


class JSONLDRelatedField(relations.HyperlinkedRelatedField):
    """
    Support of showing and saving of expanded JSON nesting or just a resource
    URL.
    Serializing is controlled by query string param 'expand', deserialization
    by format of JSON given.

    Default serializing is expand=false.
    """

    invalid_json_error = _("Incorrect JSON. Expected JSON, received %s.")
    id_missing_error = _("@id field missing")

    def __init__(self, *args, **kwargs):
        self.related_serializer = kwargs.pop("serializer", None)
        self.hide_ld_context = kwargs.pop("hide_ld_context", False)
        self.expanded = kwargs.pop("expanded", False)
        super().__init__(*args, **kwargs)

    def use_pk_only_optimization(self):
        if self.is_expanded():
            return False
        else:
            return True

    def to_representation(self, obj):
        if isinstance(self.related_serializer, str):
            app_name, file_name, class_name = self.related_serializer.split(".")
            module = importlib.import_module(f"{app_name}.{file_name}")
            self.related_serializer = getattr(module, class_name, None)

        if self.is_expanded():
            context = self.context.copy()
            # To avoid infinite recursion, only include sub/super events one level at
            # a time
            if "include" in context:
                context["include"] = [
                    x
                    for x in context["include"]
                    if x != "sub_events" and x != "super_event" and x != "registration"
                ]
            return self.related_serializer(
                obj, hide_ld_context=self.hide_ld_context, context=context
            ).data
        link = super().to_representation(obj)
        if link is None:
            return None
        return {"@id": link}

    def to_internal_value(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError(
                self.invalid_json_error % type(value).__name__
            )
        if "@id" not in value:
            raise serializers.ValidationError(self.id_missing_error)

        url = value["@id"]
        if not url:
            if self.required:
                raise serializers.ValidationError(_("This field is required."))
            return None

        return super().to_internal_value(urllib.parse.unquote(url))

    def is_expanded(self):
        return getattr(self, "expanded", False)

    def get_queryset(self):
        #  For certain related fields we preload the queryset to avoid *.objects.all() query which can easily overload  # noqa: E501
        #  the memory as database grows.
        if isinstance(self._kwargs["serializer"], str):
            return super().get_queryset()
        current_model = self._kwargs["serializer"].Meta.model
        preloaded_fields = {
            Place: "location",
            Keyword: "keywords",
            Image: "image",
            Event: "sub_events",
        }
        if current_model in preloaded_fields.keys():
            return self.context.get(preloaded_fields[current_model])
        else:
            return super().get_queryset()
