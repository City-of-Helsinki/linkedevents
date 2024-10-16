import base64
import struct
import time
import urllib
from copy import deepcopy
from datetime import timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib.gis.geos import Point
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.encoding import force_str
from django.utils.translation import gettext_lazy as _
from django_orghierarchy.models import Organization, OrganizationClass
from drf_spectacular.utils import OpenApiTypes, extend_schema_field
from munigeo.api import DEFAULT_SRS, GeoModelSerializer
from munigeo.api import TranslatedModelSerializer as ParlerTranslatedModelSerializer
from munigeo.models import AdministrativeDivision
from rest_framework import serializers
from rest_framework.exceptions import ErrorDetail, ParseError
from rest_framework.exceptions import PermissionDenied as DRFPermissionDenied
from rest_framework.fields import DateTimeField
from rest_framework_bulk import BulkListSerializer, BulkSerializerMixin

from events import utils
from events.auth import ApiKeyUser
from events.extensions import get_extensions_from_request
from events.fields import (
    EnumChoiceField,
    EventJSONLDRelatedField,
    EventsJSONLDRelatedField,
    ImagesJSONLDRelatedField,
    KeywordsJSONLDRelatedField,
    LanguagesJSONLDRelatedField,
    LocationJSONLDRelatedField,
    OrganizationUserField,
    RegistrationJSONLDRelatedField,
    StringSlugRelatedField,
)
from events.models import (
    PUBLICATION_STATUSES,
    DataSource,
    Event,
    EventLink,
    Feedback,
    Image,
    Keyword,
    KeywordSet,
    Language,
    License,
    Offer,
    Place,
    PublicationStatus,
    Video,
)
from events.utils import clean_text_fields
from linkedevents.registry import viewset_classes_by_model
from linkedevents.serializers import LinkedEventsSerializer, TranslatedModelSerializer
from linkedevents.utils import (
    get_fixed_lang_codes,
    validate_serializer_field_for_duplicates,
)
from registrations.exceptions import WebStoreAPIError
from registrations.models import OfferPriceGroup, WebStoreAccount, WebStoreMerchant
from registrations.serializers import (
    OfferPriceGroupSerializer,
    WebStoreAccountSerializer,
    WebStoreMerchantSerializer,
)

LOCAL_TZ = ZoneInfo(settings.TIME_ZONE)
EVENT_SERIALIZER_REF = "events.serializers.EventSerializer"


def _format_images_v0_1(data):
    if "images" not in data:
        return
    images = data.get("images")
    del data["images"]
    if len(images) == 0:
        data["image"] = None
    else:
        data["image"] = images[0].get("url", None)


def generate_id(namespace):
    t = time.time() * 1000
    postfix = base64.b32encode(struct.pack(">Q", int(t)).lstrip(b"\x00"))
    postfix = postfix.strip(b"=").lower().decode(encoding="UTF-8")
    return "{}:{}".format(namespace, postfix)


def _get_serializer_for_model(model, version="v1"):
    viewset_cls = viewset_classes_by_model.get(model)
    if viewset_cls is None:
        return None
    serializer = None
    if hasattr(viewset_cls, "get_serializer_class_for_version"):
        serializer = viewset_cls.get_serializer_class_for_version(version)
    elif hasattr(viewset_cls, "serializer_class"):
        serializer = viewset_cls.serializer_class
    return serializer


class DataSourceSerializer(LinkedEventsSerializer):
    view_name = "data_source-list"

    class Meta:
        model = DataSource
        exclude = ["api_key"]


class DivisionSerializer(ParlerTranslatedModelSerializer):
    type = serializers.SlugRelatedField(slug_field="type", read_only=True)
    municipality = StringSlugRelatedField(slug_field="name", read_only=True)

    class Meta:
        model = AdministrativeDivision
        fields = ("type", "ocd_id", "municipality", "translations")


class EditableLinkedEventsObjectSerializer(LinkedEventsSerializer):
    has_user_editable_resources = serializers.BooleanField(
        source="is_user_editable_resources", read_only=True
    )

    def create(self, validated_data):
        if "data_source" not in validated_data:
            validated_data["data_source"] = self.context["data_source"]
        # data source has already been validated
        if "publisher" not in validated_data:
            validated_data["publisher"] = self.context["publisher"]
        # publisher has already been validated

        request = self.context["request"]
        user = request.user
        validated_data["created_by"] = user
        validated_data["last_modified_by"] = user

        try:
            instance = super().create(validated_data)
        except IntegrityError as error:
            if "duplicate" in str(error) and "pkey" in str(error):
                raise serializers.ValidationError(
                    {"id": _("An object with given id already exists.")}
                )
            else:
                raise error
        return instance

    def update(self, instance, validated_data):
        validated_data["last_modified_by"] = self.user

        if "id" in validated_data and instance.id != validated_data["id"]:
            raise serializers.ValidationError(
                {"id": _("You may not change the id of an existing object.")}
            )
        if "publisher" in validated_data and validated_data["publisher"] not in (
            instance.publisher,
            instance.publisher.replaced_by,
        ):
            raise serializers.ValidationError(
                {
                    "publisher": _(
                        "You may not change the publisher of an existing object."
                    )
                }
            )
        if (
            "data_source" in validated_data
            and instance.data_source != validated_data["data_source"]
        ):
            raise serializers.ValidationError(
                {
                    "data_source": _(
                        "You may not change the data source of an existing object."
                    )
                }
            )
        super().update(instance, validated_data)
        return instance


class EventLinkSerializer(serializers.ModelSerializer):
    def to_representation(self, obj):
        ret = super().to_representation(obj)
        if not ret["name"]:
            ret["name"] = None
        return ret

    class Meta:
        model = EventLink
        exclude = ["id", "event"]


class FeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = Feedback
        fields = "__all__"


class ImageSerializer(EditableLinkedEventsObjectSerializer):
    view_name = "image-detail"
    license = serializers.PrimaryKeyRelatedField(
        queryset=License.objects.all(), required=False
    )
    created_time = DateTimeField(
        default_timezone=ZoneInfo("UTC"), required=False, allow_null=True
    )
    last_modified_time = DateTimeField(
        default_timezone=ZoneInfo("UTC"), required=False, allow_null=True
    )
    created_by = serializers.StringRelatedField(required=False, allow_null=True)
    last_modified_by = serializers.StringRelatedField(required=False, allow_null=True)

    class Meta:
        model = Image
        fields = "__all__"

    def to_representation(self, obj):
        # the url field is customized based on image and url
        representation = super().to_representation(obj)
        if representation["image"]:
            representation["url"] = representation["image"]
        representation.pop("image")
        return representation

    def validate(self, data):
        # name the image after the file, if name was not provided
        if "name" not in data or not data["name"]:
            if "url" in data:
                data["name"] = str(data["url"]).rsplit("/", 1)[-1]
            if "image" in data:
                data["name"] = str(data["image"]).rsplit("/", 1)[-1]
        super().validate(data)
        return data


class KeywordSerializer(EditableLinkedEventsObjectSerializer):
    id = serializers.CharField(required=False)
    view_name = "keyword-detail"
    alt_labels = serializers.SlugRelatedField(
        slug_field="name", read_only=True, many=True
    )
    created_time = DateTimeField(
        default_timezone=ZoneInfo("UTC"), required=False, allow_null=True
    )
    last_modified_time = DateTimeField(
        default_timezone=ZoneInfo("UTC"), required=False, allow_null=True
    )

    def validate_id(self, value):
        if value:
            id_data_source_prefix = value.split(":", 1)[0]
            data_source = self.context["data_source"]
            if id_data_source_prefix != data_source.id:
                # the object might be from another data source by the same organization,
                # and we are only editing it
                if (
                    self.instance
                    and self.context["publisher"]
                    .owned_systems.filter(id=id_data_source_prefix)
                    .exists()
                ):
                    return value
                raise serializers.ValidationError(
                    _(
                        "Setting id to %(given)s "
                        "is not allowed for your organization. The id "
                        "must be left blank or set to %(data_source)s:desired_id"
                    )
                    % {"given": str(value), "data_source": data_source}
                )
        return value

    def create(self, validated_data):
        # if id was not provided, we generate it upon creation:
        if "id" not in validated_data:
            validated_data["id"] = generate_id(self.context["data_source"])
        return super().create(validated_data)

    class Meta:
        model = Keyword
        exclude = ("n_events_changed",)


class KeywordSetSerializer(LinkedEventsSerializer):
    view_name = "keywordset-detail"
    keywords = KeywordsJSONLDRelatedField(
        serializer=KeywordSerializer,
        many=True,
        required=False,
        allow_empty=True,
        view_name="keyword-detail",
        queryset=Keyword.objects.none(),
    )
    usage = EnumChoiceField(KeywordSet.USAGES)
    created_time = DateTimeField(
        default_timezone=ZoneInfo("UTC"), required=False, allow_null=True
    )
    last_modified_time = DateTimeField(
        default_timezone=ZoneInfo("UTC"), required=False, allow_null=True
    )
    has_user_editable_resources = serializers.BooleanField(
        source="is_user_editable_resources", read_only=True
    )

    def to_internal_value(self, data):
        # extracting ids from the
        # '@id':'http://testserver/v1/keyword/system:tunnettu_avainsana/' type
        # record
        keyword_ids = [
            urllib.parse.unquote(i.get("@id", "").rstrip("/").split("/")[-1])
            for i in data.get("keywords", {})
        ]
        self.context["keywords"] = Keyword.objects.filter(id__in=keyword_ids)
        return super().to_internal_value(data)

    def validate_organization(self, value):
        return self.validate_publisher(
            value, field="organization", allowed_to_regular_user=False
        )

    def create(self, validated_data):
        validated_data["created_by"] = self.user
        validated_data["last_modified_by"] = self.user

        if (
            not isinstance(self.user, ApiKeyUser)
            and not validated_data["data_source"].user_editable_resources
        ):
            raise PermissionDenied()

        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data["last_modified_by"] = self.user

        if "id" in validated_data and instance.id != validated_data["id"]:
            raise serializers.ValidationError(
                {"id": _("You may not change the id of an existing object.")}
            )
        if "organization" in validated_data and validated_data["organization"] not in (
            instance.organization,
            instance.organization.replaced_by,
        ):
            raise serializers.ValidationError(
                {
                    "organization": _(
                        "You may not change the organization of an existing object."
                    )
                }
            )
        if (
            "data_source" in validated_data
            and instance.data_source != validated_data["data_source"]
        ):
            raise serializers.ValidationError(
                {
                    "data_source": _(
                        "You may not change the data source of an existing object."
                    )
                }
            )
        super().update(instance, validated_data)
        return instance

    class Meta:
        model = KeywordSet
        fields = "__all__"


class LanguageSerializer(LinkedEventsSerializer):
    view_name = "language-detail"
    translation_available = serializers.SerializerMethodField()

    class Meta:
        model = Language
        fields = "__all__"

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_translation_available(self, obj):
        return obj.id in get_fixed_lang_codes()


class OfferSerializer(TranslatedModelSerializer):
    def get_fields(self):
        fields = super().get_fields()

        if settings.WEB_STORE_INTEGRATION_ENABLED:
            fields["offer_price_groups"] = OfferPriceGroupSerializer(
                many=True,
                required=False,
            )

        return fields

    def validate_offer_price_groups(self, value):
        def error_detail_callback(price_group):
            return ErrorDetail(
                _("Offer price group with price_group %(price_group)s already exists.")
                % {"price_group": price_group},
                code="unique",
            )

        return validate_serializer_field_for_duplicates(
            value, "price_group", error_detail_callback
        )

    class Meta:
        model = Offer
        fields = ["price", "info_url", "description", "is_free"]
        if settings.WEB_STORE_INTEGRATION_ENABLED:
            fields += ("offer_price_groups",)


class OrganizationBaseSerializer(LinkedEventsSerializer):
    view_name = "organization-detail"

    class Meta:
        model = Organization
        fields = "__all__"


class OrganizationListSerializer(OrganizationBaseSerializer):
    parent_organization = serializers.HyperlinkedRelatedField(
        queryset=Organization.objects.all(),
        source="parent",
        view_name="organization-detail",
        required=False,
    )
    sub_organizations = serializers.HyperlinkedRelatedField(
        view_name="organization-detail", many=True, required=False, read_only=True
    )
    affiliated_organizations = serializers.HyperlinkedRelatedField(
        view_name="organization-detail", many=True, required=False, read_only=True
    )
    replaced_by = serializers.HyperlinkedRelatedField(
        view_name="organization-detail", required=False, read_only=True
    )
    is_affiliated = serializers.SerializerMethodField()
    has_regular_users = serializers.SerializerMethodField()
    created_time = DateTimeField(
        default_timezone=ZoneInfo("UTC"), required=False, allow_null=True
    )
    last_modified_time = DateTimeField(
        default_timezone=ZoneInfo("UTC"), required=False, allow_null=True
    )

    class Meta:
        model = Organization
        fields = (
            "id",
            "data_source",
            "origin_id",
            "classification",
            "name",
            "founding_date",
            "dissolution_date",
            "parent_organization",
            "sub_organizations",
            "affiliated_organizations",
            "created_time",
            "last_modified_time",
            "created_by",
            "last_modified_by",
            "replaced_by",
            "has_regular_users",
            "is_affiliated",
        )

    @staticmethod
    @extend_schema_field(OpenApiTypes.BOOL)
    def get_is_affiliated(obj):
        return obj.internal_type == Organization.AFFILIATED

    @staticmethod
    @extend_schema_field(OpenApiTypes.BOOL)
    def get_has_regular_users(obj):
        return obj.regular_users.count() > 0


class PlaceSerializer(EditableLinkedEventsObjectSerializer, GeoModelSerializer):
    id = serializers.CharField(required=False)
    origin_id = serializers.CharField(required=False)
    data_source = serializers.PrimaryKeyRelatedField(
        queryset=DataSource.objects.all(), required=False, allow_null=True
    )
    publisher = serializers.PrimaryKeyRelatedField(
        queryset=Organization.objects.all(), required=False, allow_null=True
    )

    view_name = "place-detail"
    divisions = DivisionSerializer(many=True, read_only=True)
    created_time = DateTimeField(
        default_timezone=ZoneInfo("UTC"), required=False, allow_null=True
    )
    last_modified_time = DateTimeField(
        default_timezone=ZoneInfo("UTC"), required=False, allow_null=True
    )

    def _handle_position(self):
        srs = self.context.get("srs", DEFAULT_SRS)
        if self.request.data["position"]:
            coord = self.request.data["position"]["coordinates"]
            if len(coord) == 2 and all([isinstance(i, float) for i in coord]):
                return Point(
                    self.request.data["position"]["coordinates"], srid=srs.srid
                )
            else:
                raise ParseError(
                    f"Two coordinates have to be provided and they should be float. You provided {coord}"  # noqa: E501
                )
        return None

    def create(self, validated_data):
        # if id was not provided, we generate it upon creation:
        if "id" not in validated_data:
            validated_data["id"] = generate_id(self.context["data_source"])
        instance = super().create(validated_data)
        if point := self._handle_position():
            instance.position = point
            instance.save()
        return instance

    def update(self, instance, validated_data):
        instance = super().update(instance, validated_data)
        if point := self._handle_position():
            instance.position = point
            instance.save()
        return instance

    class Meta:
        model = Place
        exclude = ("n_events_changed",)


class OrganizationDetailSerializer(OrganizationListSerializer):
    user_fields = [
        "admin_users",
        "financial_admin_users",
        "registration_admin_users",
        "regular_users",
    ]

    admin_users = OrganizationUserField(
        many=True,
        required=False,
    )

    registration_admin_users = OrganizationUserField(
        many=True,
        required=False,
    )

    financial_admin_users = OrganizationUserField(
        many=True,
        required=False,
    )

    regular_users = OrganizationUserField(
        many=True,
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        instance = self.instance
        user = self.context.get("user")

        if instance:
            self.fields["data_source"].read_only = True
            self.fields["origin_id"].read_only = True

            # Show organization's users only to superusers or the organization's admins.
            if user.is_anonymous or not (
                user.is_superuser or user.is_admin_of(instance)
            ):
                for field in self.user_fields:
                    self.fields.pop(field, None)

    def get_fields(self):
        fields = super().get_fields()

        if settings.WEB_STORE_INTEGRATION_ENABLED:
            common_web_store_field_kwargs = {
                "many": True,
                "required": False,
                "allow_null": True,
                "min_length": 0,
                "context": self.context,
            }

            fields["web_store_merchants"] = WebStoreMerchantSerializer(
                instance=(
                    self.instance.web_store_merchants.all() if self.instance else None
                ),
                organization=self.instance,
                **common_web_store_field_kwargs,
            )

            fields["web_store_accounts"] = WebStoreAccountSerializer(
                instance=(
                    self.instance.web_store_accounts.all() if self.instance else None
                ),
                **common_web_store_field_kwargs,
            )

        return fields

    def validate_parent_organization(self, value):
        if value:
            user = self.request.user

            if user.is_anonymous or not utils.organization_can_be_edited_by(
                value, user
            ):
                raise DRFPermissionDenied(_("User has no rights to this organization"))

        return value

    def _create_or_update_web_store_merchants(self, organization, merchants_data):
        for merchant_data in merchants_data:
            if not (merchant_id := merchant_data.pop("id", None)):
                merchant_data["created_by"] = self.request.user
            merchant_data["last_modified_by"] = self.request.user

            try:
                WebStoreMerchant.objects.update_or_create(
                    pk=merchant_id,
                    organization=organization,
                    defaults=merchant_data,
                )
            except WebStoreAPIError as exc:
                raise serializers.ValidationError(exc.messages)

    def _create_web_store_accounts(self, organization, accounts_data):
        web_store_accounts = []

        for account_data in accounts_data:
            account_data["created_by"] = self.request.user
            account_data["last_modified_by"] = self.request.user

            web_store_accounts.append(
                WebStoreAccount(
                    organization=organization,
                    **account_data,
                )
            )

        WebStoreAccount.objects.bulk_create(web_store_accounts)

    def _update_web_store_accounts(self, organization, accounts_data):
        new_accounts = []

        for account_data in accounts_data:
            if not (account_id := account_data.get("id")):
                new_accounts.append(account_data)
                continue

            account_data["last_modified_by"] = self.request.user
            WebStoreAccount.objects.update_or_create(
                pk=account_id,
                organization=organization,
                defaults=account_data,
            )

        if new_accounts:
            self._create_web_store_accounts(organization, new_accounts)

    def connect_organizations(self, connected_orgs, created_org):
        internal_types = {
            "sub_organizations": Organization.NORMAL,
            "affiliated_organizations": Organization.AFFILIATED,
        }
        for org_type in connected_orgs.keys():
            conn_org = Organization.objects.filter(
                id__in=connected_orgs[org_type], internal_type=internal_types[org_type]
            )
            created_org.children.add(*conn_org)

    @transaction.atomic
    def create(self, validated_data):
        # Add current user to admin users
        if "admin_users" not in validated_data:
            validated_data["admin_users"] = []

        if self.user not in validated_data["admin_users"]:
            validated_data["admin_users"].append(self.user)

        connected_organizations = ["sub_organizations", "affiliated_organizations"]
        conn_orgs_in_request = {}
        for org_type in connected_organizations:
            if org_type in self.request.data.keys():
                if isinstance(self.request.data[org_type], list):
                    conn_orgs_in_request[org_type] = [
                        i.rstrip("/").split("/")[-1]
                        for i in self.request.data.pop(org_type)
                    ]
                else:
                    raise ParseError(
                        f"{org_type} should be a list, you provided {type(self.request.data[org_type])}"  # noqa: E501
                    )

        web_store_merchants = validated_data.pop("web_store_merchants", None)
        web_store_accounts = validated_data.pop("web_store_accounts", None)

        org = super().create(validated_data)
        self.connect_organizations(conn_orgs_in_request, org)

        if not settings.WEB_STORE_INTEGRATION_ENABLED:
            return org

        if web_store_merchants:
            self._create_or_update_web_store_merchants(org, web_store_merchants)

        if web_store_accounts:
            self._create_web_store_accounts(org, web_store_accounts)

        return org

    @transaction.atomic
    def update(self, instance, validated_data):
        # Prevent user to accidentally remove himself from admin
        if validated_data.get("admin_users") is not None:
            admin_users = validated_data.pop("admin_users")
            instance.admin_users.set([*admin_users, self.user])

        web_store_merchants = validated_data.pop("web_store_merchants", None)
        web_store_accounts = validated_data.pop("web_store_accounts", None)

        org = super().update(instance, validated_data)

        if not settings.WEB_STORE_INTEGRATION_ENABLED:
            return org

        if web_store_merchants:
            self._create_or_update_web_store_merchants(org, web_store_merchants)

        if web_store_accounts:
            self._update_web_store_accounts(org, web_store_accounts)

        return org

    class Meta:
        model = Organization
        fields = (
            "id",
            "data_source",
            "origin_id",
            "classification",
            "name",
            "founding_date",
            "dissolution_date",
            "parent_organization",
            "sub_organizations",
            "affiliated_organizations",
            "created_time",
            "last_modified_time",
            "created_by",
            "last_modified_by",
            "is_affiliated",
            "replaced_by",
            "has_regular_users",
            "regular_users",
            "financial_admin_users",
            "registration_admin_users",
            "admin_users",
        )
        if settings.WEB_STORE_INTEGRATION_ENABLED:
            fields += ("web_store_merchants", "web_store_accounts")


class OrganizationClassSerializer(LinkedEventsSerializer):
    view_name = "organization_class-list"

    class Meta:
        model = OrganizationClass
        fields = "__all__"


class VideoSerializer(serializers.ModelSerializer):
    def to_representation(self, obj):
        ret = super().to_representation(obj)
        if not ret["name"]:
            ret["name"] = None
        return ret

    class Meta:
        model = Video
        exclude = ["id", "event"]


class EventSerializer(BulkSerializerMixin, EditableLinkedEventsObjectSerializer):
    view_name = "event-detail"
    fields_needed_to_publish = (
        "keywords",
        "location",
        "start_time",
        "short_description",
        "description",
    )
    # Personal information fields to exclude from the public API.
    personal_information_fields = (
        "user_name",
        "user_email",
        "user_phone_number",
        "user_organization",
        "user_consent",
    )

    id = serializers.CharField(required=False)
    location = LocationJSONLDRelatedField(
        serializer=PlaceSerializer,
        required=False,
        allow_null=True,
        view_name="place-detail",
    )
    keywords = KeywordsJSONLDRelatedField(
        serializer=KeywordSerializer,
        many=True,
        allow_empty=True,
        required=False,
        view_name="keyword-detail",
    )
    registration = RegistrationJSONLDRelatedField(
        serializer="registrations.serializers.RegistrationSerializer",
        many=False,
        allow_empty=True,
        required=False,
        view_name="registration-detail",
        allow_null=True,
    )
    super_event = EventJSONLDRelatedField(
        serializer=EVENT_SERIALIZER_REF,
        required=False,
        view_name="event-detail",
        allow_null=True,
        queryset=Event.objects.filter(
            Q(super_event_type=Event.SuperEventType.RECURRING)
            | Q(super_event_type=Event.SuperEventType.UMBRELLA)
        ),
    )
    event_status = EnumChoiceField(Event.STATUSES, required=False)
    type_id = EnumChoiceField(Event.TYPE_IDS, required=False)
    publication_status = EnumChoiceField(PUBLICATION_STATUSES, required=False)
    external_links = EventLinkSerializer(many=True, required=False)
    offers = OfferSerializer(many=True, required=False)
    data_source = serializers.PrimaryKeyRelatedField(
        queryset=DataSource.objects.all(), required=False
    )
    publisher = serializers.PrimaryKeyRelatedField(
        queryset=Organization.objects.all(),
        required=False,
        allow_null=True,
    )
    sub_events = EventsJSONLDRelatedField(
        serializer=EVENT_SERIALIZER_REF,
        required=False,
        view_name="event-detail",
        many=True,
        queryset=Event.objects.filter(deleted=False),
    )
    images = ImagesJSONLDRelatedField(
        serializer=ImageSerializer,
        required=False,
        allow_null=True,
        many=True,
        view_name="image-detail",
        expanded=True,
    )
    videos = VideoSerializer(many=True, required=False)
    in_language = LanguagesJSONLDRelatedField(
        serializer=LanguageSerializer,
        required=False,
        view_name="language-detail",
        many=True,
        queryset=Language.objects.all(),
    )
    audience = KeywordsJSONLDRelatedField(
        serializer=KeywordSerializer,
        view_name="keyword-detail",
        many=True,
        required=False,
    )

    created_time = DateTimeField(
        default_timezone=ZoneInfo("UTC"), required=False, allow_null=True
    )
    last_modified_time = DateTimeField(
        default_timezone=ZoneInfo("UTC"), required=False, allow_null=True
    )
    date_published = DateTimeField(
        default_timezone=ZoneInfo("UTC"), required=False, allow_null=True
    )
    start_time = DateTimeField(
        default_timezone=ZoneInfo("UTC"), required=False, allow_null=True
    )
    end_time = DateTimeField(
        default_timezone=ZoneInfo("UTC"), required=False, allow_null=True
    )
    created_by = serializers.StringRelatedField(required=False, allow_null=True)
    last_modified_by = serializers.StringRelatedField(required=False, allow_null=True)

    class Meta:
        model = Event
        exclude = (
            "search_vector_en",
            "search_vector_fi",
            "search_vector_sv",
        )
        list_serializer_class = BulkListSerializer

    def __init__(self, *args, skip_empties=False, **kwargs):
        super().__init__(*args, **kwargs)
        # The following can be used when serializing when
        # testing and debugging.
        self.skip_empties = skip_empties
        if self.context:
            for ext in self.context.get("extensions", ()):
                self.fields["extension_{}".format(ext.identifier)] = (
                    ext.get_extension_serializer()
                )

            user = self.context["request"].user

            if not settings.ENABLE_EXTERNAL_USER_EVENTS:
                for field in self.personal_information_fields:
                    self.fields.pop(field, None)
            elif user.is_authenticated and user.is_external:
                for field in ("user_name", "maximum_attendee_capacity"):
                    self.fields[field].required = True

    def parse_datetimes(self, data):
        # here, we also set has_start_time and has_end_time accordingly
        for field in ["date_published", "start_time", "end_time"]:
            val = data.get(field, None)
            if val and isinstance(val, str):
                if field == "end_time":
                    dt, is_date = utils.parse_end_time(val)
                else:
                    dt, is_date = utils.parse_time(val)

                data[field] = dt
                data[f"has_{field}"] = not is_date
        return data

    def to_internal_value(self, data):
        data = self.parse_datetimes(data)
        data = super().to_internal_value(data)
        return data

    def validate_keywords(self, keywords):
        for kw in keywords:
            if kw.deprecated:
                raise serializers.ValidationError(
                    _("Deprecated keyword not allowed ({})").format(kw.pk)
                )
        return keywords

    def validate_audience(self, audiences):
        return self.validate_keywords(audiences)

    def validate_external_links(self, value):
        if not value:
            return value

        for index, link in enumerate(value):
            # clean link text fields
            value[index] = clean_text_fields(link)

        checked_values = set()
        for data in value:
            name = data.get("name", "")
            language = data["language"].pk
            link = data["link"]

            unique_link = f"{name}-{language}-{link}".lower()
            if unique_link in checked_values:
                raise serializers.ValidationError(
                    {
                        "name": _("Duplicate link given with name %(name)s.")
                        % {"name": name},
                        "language": _(
                            "Duplicate link given with language %(language)s."
                        )
                        % {"language": language},
                        "link": _("Duplicate link given with link %(link)s.")
                        % {"link": link},
                    }
                )

            checked_values.add(unique_link)

        return value

    def validate(self, data):
        context = self.context
        user = self.context["request"].user
        # clean all text fields, only description may contain any html
        data = clean_text_fields(data, allowed_html_fields=["description"])

        data = super().validate(data)

        if "publication_status" not in data:
            data["publication_status"] = PublicationStatus.PUBLIC

        # If the event is a draft, postponed or cancelled, no further validation is performed  # noqa: E501
        # For external users do all validations.
        if (
            data["publication_status"] == PublicationStatus.DRAFT
            or data.get("event_status", None) == Event.Status.CANCELLED
            or (
                self.context["request"].method == "PUT"
                and "start_time" in data
                and not data["start_time"]
            )
        ):
            data = self.run_extension_validations(data)

            if not (
                settings.ENABLE_EXTERNAL_USER_EVENTS
                and user.is_authenticated
                and user.is_external
            ):
                return data

        # check that published events have a location, keyword and start_time
        languages = get_fixed_lang_codes()

        errors = {}

        if (
            settings.ENABLE_EXTERNAL_USER_EVENTS
            and user.is_authenticated
            and user.is_external
        ):
            if not (data.get("user_email") or data.get("user_phone_number")):
                # External users need to fill either email or phone number
                error = _("You have to set either user_email or user_phone_number.")
                errors["user_email"] = error
                errors["user_phone_number"] = error

        has_filled_personal_information = any(
            map(lambda x: bool(data.get(x)), self.personal_information_fields)
        )
        if has_filled_personal_information and not data.get("user_consent"):
            errors["user_consent"] = _(
                "User consent is required if personal information fields are filled."
            )

        lang_error_msg = _("This field must be specified before an event is published.")
        for field in self.fields_needed_to_publish:
            if field in self.translated_fields:
                for lang in languages:
                    name = "name_%s" % lang
                    field_lang = "%s_%s" % (field, lang)
                    if data.get(name) and not data.get(field_lang):
                        errors.setdefault(field, {})[lang] = lang_error_msg
                    if (
                        data.get(field_lang)
                        and field == "short_description"
                        and len(data.get(field_lang, [])) > 160
                    ):
                        errors.setdefault(field, {})[lang] = _(
                            "Short description length must be 160 characters or less"
                        )

            elif not data.get(field):
                errors[field] = lang_error_msg

        # published events need price info = at least one offer that is free or not
        offer_exists = False
        for index, offer in enumerate(data.get("offers", [])):
            if "is_free" in offer:
                offer_exists = True
            # clean offer text fields
            data["offers"][index] = clean_text_fields(offer)

        if not offer_exists:
            errors["offers"] = _(
                "Price info must be specified before an event is published."
            )

        # clean video text fields
        for index, video in enumerate(data.get("video", [])):
            # clean link text fields
            data["video"][index] = clean_text_fields(video)

        # If no end timestamp supplied, we treat the event as ending at midnight
        if not data.get("end_time"):
            # The start time may also be null if the event is postponed
            if not data.get("start_time"):
                data["has_end_time"] = False
                data["end_time"] = None
            else:
                data["has_end_time"] = False
                data["end_time"] = utils.start_of_next_day(data["start_time"])

        data_source = context["data_source"]
        past_allowed = data_source.create_past_events
        if self.instance:
            past_allowed = data_source.edit_past_events

        if (
            data.get("end_time")
            and data["end_time"] < timezone.now()
            and not past_allowed
        ):
            errors["end_time"] = force_str(
                _("End time cannot be in the past. Please set a future end time.")
            )

        if errors:
            raise serializers.ValidationError(errors)

        data = self.run_extension_validations(data)

        return data

    def run_extension_validations(self, data):
        for ext in self.context.get("extensions", ()):
            new_data = ext.validate_event_data(self, data)
            if new_data:
                data = new_data
        return data

    @staticmethod
    def _create_or_update_offers(offers, event, update=False):
        if not isinstance(offers, list):
            return

        if update:
            event.offers.all().delete()

        for offer in offers:
            offer_price_groups = offer.pop("offer_price_groups", [])

            offer = Offer.objects.create(event=event, **offer)

            if not settings.WEB_STORE_INTEGRATION_ENABLED:
                continue

            for offer_price_group in offer_price_groups:
                OfferPriceGroup.objects.create(offer=offer, **offer_price_group)

    def create(self, validated_data):
        # if id was not provided, we generate it upon creation:
        data_source = self.context["data_source"]
        request = self.context["request"]
        user = request.user

        if "id" not in validated_data:
            validated_data["id"] = generate_id(data_source)

        offers = validated_data.pop("offers", [])
        links = validated_data.pop("external_links", [])
        videos = validated_data.pop("videos", [])

        validated_data.update(
            {
                "created_by": user,
                "last_modified_by": user,
                "created_time": Event.now(),  # we must specify creation time as we are setting id  # noqa: E501
                "event_status": Event.Status.SCHEDULED,
                # mark all newly created events as scheduled
            }
        )

        if settings.ENABLE_EXTERNAL_USER_EVENTS and user.is_external:
            validated_data["publisher"] = (
                validated_data.get("publisher")
                or utils.get_or_create_default_organization()
            )

        # pop out extension related fields because create() cannot stand them
        original_validated_data = deepcopy(validated_data)
        for field_name, field in self.fields.items():
            if field_name.startswith("extension_") and field.source in validated_data:
                validated_data.pop(field.source)

        event = super().create(validated_data)

        # create and add related objects
        self._create_or_update_offers(offers, event)

        for link in links:
            EventLink.objects.create(event=event, **link)

        for video in videos:
            Video.objects.create(event=event, **video)

        extensions = get_extensions_from_request(request)

        for ext in extensions:
            ext.post_create_event(
                request=request, event=event, data=original_validated_data
            )

        return event

    def update(self, instance, validated_data):
        offers = validated_data.pop("offers", None)
        links = validated_data.pop("external_links", None)
        videos = validated_data.pop("videos", None)
        data_source = self.context["data_source"]
        publisher = validated_data.get("publisher") or instance.publisher

        validated_data.update({"publisher": publisher})

        if (
            instance.end_time
            and instance.end_time < timezone.now()
            and not data_source.edit_past_events
        ):
            raise DRFPermissionDenied(_("Cannot edit a past event."))

        # The API only allows scheduling and cancelling events.
        # POSTPONED and RESCHEDULED may not be set, but should be allowed in
        # already set instances.
        if (
            validated_data.get("event_status")
            in (
                Event.Status.POSTPONED,
                Event.Status.RESCHEDULED,
            )
            and validated_data.get("event_status") != instance.event_status
        ):
            raise serializers.ValidationError(
                {
                    "event_status": _(
                        "POSTPONED and RESCHEDULED statuses cannot be set directly."
                        "Changing event start_time or marking start_time null"
                        "will reschedule or postpone an event."
                    )
                }
            )

        # Update event_status if a PUBLIC SCHEDULED or CANCELLED event start_time is updated.  # noqa: E501
        # DRAFT events will remain SCHEDULED up to publication.
        # Check that the event is not explicitly CANCELLED at the same time.
        if (
            instance.publication_status == PublicationStatus.PUBLIC
            and validated_data.get("event_status", Event.Status.SCHEDULED)
            != Event.Status.CANCELLED
        ):
            # if the instance was ever CANCELLED, RESCHEDULED or POSTPONED, it may
            # never be SCHEDULED again
            if instance.event_status != Event.Status.SCHEDULED:
                if validated_data.get("event_status") == Event.Status.SCHEDULED:
                    raise serializers.ValidationError(
                        {
                            "event_status": _(
                                "Public events cannot be set back to SCHEDULED if they"
                                "have already been CANCELLED, POSTPONED or RESCHEDULED."
                            )
                        }
                    )
                validated_data["event_status"] = instance.event_status
            try:
                # if the start_time changes, reschedule the event
                if validated_data["start_time"] != instance.start_time:
                    validated_data["event_status"] = Event.Status.RESCHEDULED
                # if the posted start_time is null, postpone the event
                if not validated_data["start_time"]:
                    validated_data["event_status"] = Event.Status.POSTPONED
            except KeyError:
                # if the start_time is not provided, do nothing
                pass

        # pop out extension related fields because update() cannot stand them
        original_validated_data = deepcopy(validated_data)
        for field_name, field in self.fields.items():
            if field_name.startswith("extension_") and field.source in validated_data:
                validated_data.pop(field.source)

        # update validated fields
        super().update(instance, validated_data)

        # update offers
        self._create_or_update_offers(offers, instance, update=True)

        # update ext links
        if isinstance(links, list):
            instance.external_links.all().delete()
            for link in links:
                EventLink.objects.create(event=instance, **link)

        # update videos
        if isinstance(videos, list):
            instance.videos.all().delete()
            for video in videos:
                Video.objects.create(event=instance, **video)

        request = self.context["request"]
        extensions = get_extensions_from_request(request)

        for ext in extensions:
            ext.post_update_event(
                request=request, event=instance, data=original_validated_data
            )

        return instance

    def to_representation(self, obj):
        ret = super().to_representation(obj)

        if obj.deleted:
            keys_to_preserve = [
                "id",
                "name",
                "last_modified_time",
                "deleted",
                "replaced_by",
            ]
            for key in ret.keys() - keys_to_preserve:
                del ret[key]
            ret["name"] = utils.get_deleted_object_name()
            return ret

        # Remove personal information fields from public API
        user = self.context["request"].user
        if (
            not settings.ENABLE_EXTERNAL_USER_EVENTS
            or not (
                user.is_authenticated
                and (
                    user.is_regular_user_of(obj.publisher)
                    or user.is_admin_of(obj.publisher)
                )
            )
            and obj.created_by != user
        ):
            for field in self.personal_information_fields:
                if field in ret:
                    del ret[field]

        if self.context["request"].accepted_renderer.format == "docx":
            ret["end_time_obj"] = obj.end_time
            ret["start_time_obj"] = obj.start_time
            ret["location"] = obj.location

        if obj.start_time and not obj.has_start_time:
            # Return only the date part
            ret["start_time"] = obj.start_time.astimezone(LOCAL_TZ).strftime("%Y-%m-%d")
        if obj.end_time and not obj.has_end_time:
            # If the event is short (<24h), then no need for end time
            if obj.start_time and obj.end_time - obj.start_time <= timedelta(days=1):
                ret["end_time"] = None

            else:
                # If we're storing only the date part, do not pretend we have the exact time.  # noqa: E501
                # Timestamp is of the form %Y-%m-%dT00:00:00, so we report the previous
                # date.
                ret["end_time"] = utils.start_of_previous_day(obj.end_time).strftime(
                    "%Y-%m-%d"
                )

        del ret["has_start_time"]
        del ret["has_end_time"]
        if hasattr(obj, "days_left"):
            ret["days_left"] = int(obj.days_left)
        if self.skip_empties:
            for k in list(ret.keys()):
                val = ret[k]
                try:
                    if val is None or len(val) == 0:
                        del ret[k]
                except TypeError:
                    # not list/dict
                    pass
        request = self.context.get("request")
        if request and not request.user.is_authenticated:
            del ret["publication_status"]

        return ret


class EventSerializerV0_1(EventSerializer):  # noqa: N801
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("context", {}).setdefault("include", []).append("image")
        super().__init__(*args, **kwargs)

    def to_representation(self, obj):
        ret = super().to_representation(obj)
        _format_images_v0_1(ret)
        return ret


class SearchSerializer(serializers.Serializer):
    def to_representation(self, search_result):
        model = search_result.model
        version = self.context["request"].version
        ser_class = _get_serializer_for_model(model, version=version)
        assert ser_class is not None, "Serializer for %s not found" % model
        data = ser_class(search_result.object, context=self.context).data
        data["resource_type"] = model._meta.model_name
        data["score"] = search_result.score
        return data


class SearchSerializerV0_1(SearchSerializer):  # noqa: N801
    def to_representation(self, search_result):
        ret = super().to_representation(search_result)
        if "resource_type" in ret:
            ret["object_type"] = ret["resource_type"]
            del ret["resource_type"]
        return ret
