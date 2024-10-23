from typing import Optional

from django.conf import settings
from django.urls import NoReverseMatch
from django.utils.translation import gettext_lazy as _
from modeltranslation.translator import NotRegistered, translator
from rest_framework import relations, serializers
from rest_framework.exceptions import PermissionDenied as DRFPermissionDenied
from rest_framework.reverse import reverse

from linkedevents import utils
from linkedevents.fields import JSONLDRelatedField


class MPTTModelSerializer(serializers.ModelSerializer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in "lft", "rght", "tree_id", "level":
            if field_name in self.fields:
                del self.fields[field_name]


class TranslatedModelSerializer(serializers.ModelSerializer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        model = self.Meta.model
        try:
            trans_opts = translator.get_options_for_model(model)
        except NotRegistered:
            self.translated_fields = []
            return

        if (
            meta_fields := getattr(self.Meta, "fields", None)
        ) and meta_fields != serializers.ALL_FIELDS:
            self.translated_fields = [
                field for field in trans_opts.all_fields.keys() if field in meta_fields
            ]
        elif meta_excluded_fields := getattr(self.Meta, "exclude", None):
            self.translated_fields = [
                field
                for field in trans_opts.all_fields.keys()
                if field not in meta_excluded_fields
            ]
        else:
            self.translated_fields = trans_opts.all_fields.keys()

        lang_codes = utils.get_fixed_lang_codes()
        # Remove the pre-existing data in the bundle.
        for field_name in self.translated_fields:
            for lang in lang_codes:
                key = "%s_%s" % (field_name, lang)
                if key in self.fields:
                    del self.fields[key]
            del self.fields[field_name]

    def to_representation(self, obj):
        ret = super().to_representation(obj)
        if obj is None:
            return ret
        return self.translated_fields_to_representation(obj, ret)

    def to_internal_value(self, data):
        """
        Convert complex translated json objects to flat format.
        E.g. json structure containing `name` key like this:
        {
            "name": {
                "fi": "musiikkiklubit",
                "sv": "musikklubbar",
                "en": "music clubs"
            },
            ...
        }
        Transforms this:
        {
            "name": "musiikkiklubit",
            "name_fi": "musiikkiklubit",
            "name_sv": "musikklubbar",
            "name_en": "music clubs"
            ...
        }
        :param data:
        :return:
        """

        extra_fields = {}  # will contain the transformation result
        for field_name in self.translated_fields:
            obj = data.get(field_name, None)  # { "fi": "musiikkiklubit", "sv": ... }
            if not obj:
                continue
            if not isinstance(obj, dict):
                raise serializers.ValidationError(
                    {
                        field_name: "This field is a translated field. Instead of a string,"  # noqa: E501
                        " you must supply an object with strings corresponding"
                        " to desired language ids."
                    }
                )
            for language in (
                lang for lang in utils.get_fixed_lang_codes() if lang in obj
            ):
                value = obj[language]  # "musiikkiklubit"
                if language == settings.LANGUAGES[0][0]:  # default language
                    extra_fields[field_name] = value  # { "name": "musiikkiklubit" }
                extra_fields["{}_{}".format(field_name, language)] = (
                    value  # { "name_fi": "musiikkiklubit" }
                )
            del data[field_name]  # delete original translated fields

        # handle other than translated fields
        data = super().to_internal_value(data)

        # add translated fields to the final result
        data.update(extra_fields)

        return data

    def translated_fields_to_representation(self, obj, ret):
        for field_name in self.translated_fields:
            d = {}
            for lang in utils.get_fixed_lang_codes():
                key = "%s_%s" % (field_name, lang)
                val = getattr(obj, key, None)
                if val is None:
                    continue
                d[lang] = val

            # If no text provided, leave the field as null
            for _key, val in d.items():
                if val is not None:
                    break
            else:
                d = None
            ret[field_name] = d

        return ret


class LinkedEventsSerializer(TranslatedModelSerializer, MPTTModelSerializer):
    """Serializer with the support for JSON-LD/Schema.org.
    JSON-LD/Schema.org syntax::
      {
         "@context": "http://schema.org",
         "@type": "Event",
         "name": "Event name",
         ...
      }
    See full example at: http://schema.org/Event
    Args:
      hide_ld_context (bool):
        Hides `@context` from JSON, can be used in nested
        serializers
    """

    system_generated_fields = (
        "created_time",
        "last_modified_time",
        "created_by",
        "last_modified_by",
    )
    only_admin_visible_fields = ("created_by", "last_modified_by")

    def __init__(
        self,
        *args,
        skip_fields: Optional[set] = None,
        hide_ld_context=False,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        context = self.context

        if skip_fields is None:
            skip_fields = set()

        self.skip_fields = skip_fields

        if "request" in context:
            self.request = context["request"]

        # for post and put methods as well as field visibility, user information
        # is needed
        if "user" in context:
            self.user = context["user"]
        if "admin_tree_ids" in context:
            self.admin_tree_ids = context["admin_tree_ids"]

        # query allows non-skipped fields to be expanded
        include_fields = context.get("include", [])
        for field_name in include_fields:
            if field_name not in self.fields:
                continue
            field = self.fields[field_name]
            if isinstance(field, relations.ManyRelatedField):
                field = field.child_relation
            if not isinstance(field, JSONLDRelatedField):
                continue
            field.expanded = True
        # query allows additional fields to be skipped
        self.skip_fields |= context.get("skip_fields", set())

        self.hide_ld_context = hide_ld_context

    def are_only_admin_visible_fields_allowed(self, obj):
        return (
            self.user
            and hasattr(obj, "publisher")
            and obj.publisher
            and obj.publisher.tree_id in self.admin_tree_ids
        )

    def to_internal_value(self, data):
        for field in self.system_generated_fields:
            if field in data:
                del data[field]
        data = super().to_internal_value(data)
        return data

    def _prepare_representation_id(self, ret):
        if "id" not in ret or "request" not in self.context:
            return

        try:
            ret["@id"] = reverse(
                self.view_name,
                kwargs={"pk": ret["id"]},
                request=self.context["request"],
            )
        except NoReverseMatch:
            ret["@id"] = str(ret["id"])

    def _prepare_representation_context(self, ret, obj):
        # Context is hidden if:
        # 1) hide_ld_context is set to True
        # 2) self.object is None, e.g. we are in the list of stuff
        if self.hide_ld_context or self.instance is None:
            return

        if hasattr(obj, "jsonld_context") and isinstance(
            obj.jsonld_context, (dict, list)
        ):
            ret["@context"] = obj.jsonld_context
        else:
            ret["@context"] = "http://schema.org"

    def _prepare_representation_type(self, ret, obj):
        # Use jsonld_type attribute if present,
        # if not fallback to automatic resolution by model name.
        # Note: Plan 'type' could be aliased to @type in context definition to
        # conform JSON-LD spec.
        if hasattr(obj, "jsonld_type"):
            ret["@type"] = obj.jsonld_type
        else:
            ret["@type"] = obj.__class__.__name__

    def _prepare_representation_non_public_fields(self, ret, obj):
        # Display non-public fields if
        # 1) obj has publisher org, and
        # 2) user belongs to the same org tree.
        # Never modify self.skip_fields, as it survives multiple calls in the
        # serializer across objects.
        obj_skip_fields = set(self.skip_fields)
        if not self.are_only_admin_visible_fields_allowed(obj):
            obj_skip_fields |= set(self.only_admin_visible_fields)

        for field in obj_skip_fields:
            if field in ret:
                del ret[field]

    def to_representation(self, obj):
        """
        Before sending to renderer there's a need to do additional work on
        to-be-JSON dictionary data:
            1. Add @context, @type and @id fields
        Renderer is the right place for this but now loop is done just once.
        Reversal conversion is done in parser.
        """
        ret = super().to_representation(obj)

        self._prepare_representation_id(ret)
        self._prepare_representation_context(ret, obj)
        self._prepare_representation_type(ret, obj)
        self._prepare_representation_non_public_fields(ret, obj)

        return ret

    def validate_data_source(self, value):
        # a single POST always comes from a single source
        data_source = self.context["data_source"]
        if value and self.context["request"].method == "POST":
            if value != data_source:
                raise DRFPermissionDenied(
                    {
                        "data_source": _(
                            "Setting data_source to %(given)s "
                            " is not allowed for this user. The data_source"
                            " must be left blank or set to %(required)s "
                        )
                        % {"given": str(value), "required": data_source}
                    }
                )
        return value

    def validate_id(self, value):
        # a single POST always comes from a single source
        data_source = self.context["data_source"]
        if value and self.context["request"].method == "POST":
            id_data_source_prefix = value.split(":", 1)[0]
            if id_data_source_prefix != data_source.id:
                # if we are creating, there's no excuse to have any other data source
                # than the request gave
                raise serializers.ValidationError(
                    _(
                        "Setting id to %(given)s "
                        "is not allowed for your organization. The id "
                        "must be left blank or set to %(data_source)s:desired_id"
                    )
                    % {"given": str(value), "data_source": data_source}
                )
        return value

    def _validate_publisher_for_org_user(
        self, value, field="publisher", allowed_to_regular_user=True
    ):
        allowed_organizations = set(
            self.user.get_admin_organizations_and_descendants()
        ) | set(
            map(
                lambda x: x.replaced_by,
                self.user.get_admin_organizations_and_descendants(),
            )
        )

        # Allow regular users to post if allowed_to_regular_user is True
        if allowed_to_regular_user:
            allowed_organizations |= set(
                self.user.organization_memberships.all()
            ) | set(
                map(
                    lambda x: x.replaced_by,
                    self.user.organization_memberships.all(),
                )
            )

        if value not in allowed_organizations:
            publisher = self.context.get("publisher")
            publisher = publisher.replaced_by or publisher if publisher else None

            raise serializers.ValidationError(
                _(
                    "Setting %(field)s to %(given)s "
                    "is not allowed for this user. The %(field)s "
                    "must be left blank or set to %(required)s or any other organization "  # noqa: E501
                    "the user belongs to."
                )
                % {
                    "field": str(field),
                    "given": str(value),
                    "required": str(publisher),
                }
            )

    def validate_publisher(
        self, value, field="publisher", allowed_to_regular_user=True
    ):
        # a single POST always comes from a single source
        if value and self.context["request"].method == "POST":
            if self.user.is_superuser:
                return value.replaced_by if value.replaced_by else value

            self._validate_publisher_for_org_user(
                value, field=field, allowed_to_regular_user=allowed_to_regular_user
            )

            if value.replaced_by:
                # for replaced organizations, we automatically update to the current organization  # noqa: E501
                # even if the POST uses the old id
                return value.replaced_by

        return value

    def validate(self, data):
        if "name" in self.translated_fields:
            name_exists = False
            languages = [x[0] for x in settings.LANGUAGES]
            for language in languages:
                # null or empty strings are not allowed, they are the same as missing
                # name!
                name_lang_key = "name_%s" % language
                if (
                    data.get(name_lang_key)
                    or self.partial is True
                    and name_lang_key not in data
                ):
                    name_exists = True
                    break
        else:
            # null or empty strings are not allowed, they are the same as missing name!
            name_exists = (
                "name" in data
                and data["name"]
                or self.partial is True
                and "name" not in data
            )

        if not name_exists:
            raise serializers.ValidationError(
                {"name": _("The name must be specified.")}
            )

        data = super().validate(data)
        return data
