from django_orghierarchy.models import Organization
from munigeo.api import GeoModelSerializer
from rest_framework import serializers

from events.fields import EnumChoiceField
from events.models import (
    PUBLICATION_STATUSES,
    DataSource,
    Event,
    Keyword,
    Language,
    Offer,
    Place,
)
from events.serializers import DivisionSerializer
from linkedevents.serializers import TranslatedModelSerializer
from registrations.models import Registration, SignUp


class DataAnalyticsCreatedModifiedBaseSerializer(serializers.ModelSerializer):
    class Meta:
        fields = (
            "created_time",
            "last_modified_time",
        )


class DataAnalyticsAdministrativeDivisionSerializer(DivisionSerializer):
    class Meta(DivisionSerializer.Meta):
        fields = (
            "id",
            "modified_at",
            "type",
            "ocd_id",
            "municipality",
            "translations",
        )


class DataAnalyticsDataSourceSerializer(serializers.ModelSerializer):
    owner = serializers.PrimaryKeyRelatedField(read_only=True)
    has_api_key = serializers.SerializerMethodField()

    def get_has_api_key(self, obj):
        return bool(obj.api_key)

    class Meta:
        model = DataSource
        fields = (
            "id",
            "name",
            "has_api_key",
            "owner",
        )


class DataAnalyticsKeywordSerializer(
    DataAnalyticsCreatedModifiedBaseSerializer, TranslatedModelSerializer
):
    alt_labels = serializers.SlugRelatedField(
        slug_field="name", many=True, read_only=True
    )

    class Meta(DataAnalyticsCreatedModifiedBaseSerializer.Meta):
        model = Keyword
        fields = (
            "id",
            "name",
            "deprecated",
            "alt_labels",
            "n_events",
        )
        fields += DataAnalyticsCreatedModifiedBaseSerializer.Meta.fields


class DataAnalyticsPlaceSerializer(
    DataAnalyticsCreatedModifiedBaseSerializer,
    TranslatedModelSerializer,
    GeoModelSerializer,
):
    parent = serializers.PrimaryKeyRelatedField(read_only=True)
    replaced_by = serializers.PrimaryKeyRelatedField(read_only=True)
    divisions = serializers.PrimaryKeyRelatedField(many=True, read_only=True)

    class Meta(DataAnalyticsCreatedModifiedBaseSerializer.Meta):
        model = Place
        fields = (
            "id",
            "name",
            "parent",
            "replaced_by",
            "position",
            "address_country",
            "address_region",
            "address_locality",
            "postal_code",
            "post_office_box_num",
            "divisions",
            "deleted",
            "n_events",
        )
        fields += DataAnalyticsCreatedModifiedBaseSerializer.Meta.fields


class DataAnalyticsLanguageSerializer(TranslatedModelSerializer):
    class Meta:
        model = Language
        fields = ("id", "name", "service_language")


class DataAnalyticsOfferSerializer(serializers.ModelSerializer):
    class Meta:
        model = Offer
        fields = (
            "id",
            "price",
            "is_free",
        )


class DataAnalyticsOrganizationSerializer(
    DataAnalyticsCreatedModifiedBaseSerializer, TranslatedModelSerializer
):
    classification = serializers.PrimaryKeyRelatedField(read_only=True)
    parent = serializers.PrimaryKeyRelatedField(read_only=True)
    data_source = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta(DataAnalyticsCreatedModifiedBaseSerializer.Meta):
        model = Organization
        fields = (
            "id",
            "data_source",
            "name",
            "classification",
            "parent",
            "internal_type",
            "dissolution_date",
        )
        fields += DataAnalyticsCreatedModifiedBaseSerializer.Meta.fields


class DataAnalyticsEventSerializer(
    DataAnalyticsCreatedModifiedBaseSerializer, TranslatedModelSerializer
):
    publisher = serializers.PrimaryKeyRelatedField(read_only=True)
    replaced_by = serializers.PrimaryKeyRelatedField(read_only=True)
    super_event = serializers.PrimaryKeyRelatedField(read_only=True)
    location = serializers.PrimaryKeyRelatedField(read_only=True)
    in_language = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    keywords = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    audience = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    offers = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    event_status = EnumChoiceField(Event.STATUSES, required=False)
    type_id = EnumChoiceField(Event.TYPE_IDS, required=False)
    publication_status = EnumChoiceField(PUBLICATION_STATUSES, required=False)

    class Meta(DataAnalyticsCreatedModifiedBaseSerializer.Meta):
        model = Event
        fields = (
            "id",
            "name",
            "publisher",
            "deleted",
            "date_published",
            "provider",
            "event_status",
            "publication_status",
            "location",
            "environment",
            "start_time",
            "end_time",
            "has_start_time",
            "has_end_time",
            "super_event",
            "super_event_type",
            "type_id",
            "local",
            "in_language",
            "replaced_by",
            "maximum_attendee_capacity",
            "minimum_attendee_capacity",
            "enrolment_start_time",
            "enrolment_end_time",
            "keywords",
            "audience",
            "audience_min_age",
            "audience_max_age",
            "offers",
        )
        fields += DataAnalyticsCreatedModifiedBaseSerializer.Meta.fields


class DataAnalyticsSignUpSerializer(DataAnalyticsCreatedModifiedBaseSerializer):
    signup_group = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta(DataAnalyticsCreatedModifiedBaseSerializer.Meta):
        model = SignUp
        fields = (
            "id",
            "signup_group",
            "deleted",
            "attendee_status",
            "presence_status",
        )
        fields += DataAnalyticsCreatedModifiedBaseSerializer.Meta.fields


class DataAnalyticsRegistrationSerializer(DataAnalyticsCreatedModifiedBaseSerializer):
    event = serializers.PrimaryKeyRelatedField(read_only=True)
    signup_groups = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    signups = serializers.PrimaryKeyRelatedField(many=True, read_only=True)

    class Meta(DataAnalyticsCreatedModifiedBaseSerializer.Meta):
        model = Registration
        fields = (
            "id",
            "event",
            "attendee_registration",
            "audience_min_age",
            "audience_max_age",
            "enrolment_start_time",
            "enrolment_end_time",
            "maximum_attendee_capacity",
            "minimum_attendee_capacity",
            "waiting_list_capacity",
            "maximum_group_size",
            "remaining_attendee_capacity",
            "remaining_waiting_list_capacity",
            "signup_groups",
            "signups",
        )
        fields += DataAnalyticsCreatedModifiedBaseSerializer.Meta.fields
