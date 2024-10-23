from django.conf import settings
from drf_spectacular.extensions import (
    OpenApiAuthenticationExtension,
    OpenApiSerializerExtension,
)
from drf_spectacular.plumbing import build_bearer_security_scheme_object
from helusers.settings import api_token_auth_settings

from events.auth import ApiKeyAuthentication, ApiTokenAuthentication
from events.models import Event, Image, Keyword, KeywordSet, Language, Offer, Place
from events.serializers import (
    DataSourceSerializer,
    EventLinkSerializer,
    EventSerializer,
    ImageSerializer,
    KeywordSerializer,
    KeywordSetSerializer,
    LanguageSerializer,
    OfferSerializer,
    OrganizationClassSerializer,
    OrganizationDetailSerializer,
    OrganizationListSerializer,
    PlaceSerializer,
    VideoSerializer,
)
from linkedevents.schema_utils import get_custom_data_schema
from linkedevents.utils import get_fixed_lang_codes


class ApiKeyAuthenticationExtension(OpenApiAuthenticationExtension):
    target_class = ApiKeyAuthentication
    name = "Apikey"

    def get_security_definition(self, auto_schema):
        return {
            "type": "apiKey",
            "in": "header",
            "name": "apikey",
            "description": (
                "Apikey authentication for trusted data sources. Issued by Linked Events."  # noqa: E501
            ),
        }


class ApiTokenAuthenticationExtension(OpenApiAuthenticationExtension):
    target_class = ApiTokenAuthentication
    name = "Helsinki-tunnistus Keycloak"

    def get_security_definition(self, auto_schema):
        security_definition = build_bearer_security_scheme_object(
            header_name="AUTHORIZATION",
            token_prefix=api_token_auth_settings.AUTH_SCHEME or "Bearer",
            bearer_format="JWT",
        )
        security_definition["description"] = "JWT issued by Helsinki-tunnistus."

        return security_definition


class DataSourceSerializerExtension(OpenApiSerializerExtension):
    target_class = DataSourceSerializer

    def map_serializer(self, auto_schema, direction):
        result = super().map_serializer(auto_schema, direction)

        result["description"] = (
            "Source of the data, typically API provider specific identifier. Will also be used "  # noqa: E501
            "to specify standardized namespaces as they are brought into use."
        )

        result["properties"]["id"]["description"] = "Identifier of the data source."
        result["properties"]["name"]["description"] = "Name of the data source."
        result["properties"]["user_editable_resources"]["description"] = (
            "Boolean to define if resources maybe be edited by users."
        )
        result["properties"]["user_editable_organizations"]["description"] = (
            "Boolean to define if organizations may be edited by users."
        )
        result["properties"]["edit_past_events"]["description"] = (
            "Boolean to define if past events may be created using API."
        )
        result["properties"]["create_past_events"]["description"] = (
            "Boolean to define if past events may be created using API."
        )
        result["properties"]["private"]["description"] = (
            "Boolean to define is data source private. By default events of private data source "  # noqa: E501
            "are hidden."
        )
        result["properties"]["owner"]["description"] = (
            "Owner organization of the data source."
        )

        return result


class EventSerializerExtension(OpenApiSerializerExtension):
    target_class = EventSerializer

    def map_serializer(self, auto_schema, direction):
        result = super().map_serializer(auto_schema, direction)

        result["description"] = (
            "Describes the actual events. Linked events API supports organizing events into "  # noqa: E501
            'hierarchies. This is implemented with collection events called "super events". '  # noqa: E501
            "Super events are normal event objects, that reference contained events in "
            '"sub_events" property. Currently there are two major use cases: events such '  # noqa: E501
            'as "Helsinki Festival", which consist of unique events over a span of time and '  # noqa: E501
            "recurring events such as theatrical productions with multiple showings. It is "  # noqa: E501
            "implementation dependent how the grouping of events is done. It should be noted "  # noqa: E501
            "that grouping might be automatic based on eg. event name and thus group unrelated "  # noqa: E501
            "events together and miss related events. Users of data are advised to prepare for "  # noqa: E501
            "this."
        )

        result["properties"]["id"]["description"] = (
            "Consists of source prefix and source specific identifier. These should be URIs "  # noqa: E501
            "uniquely identifying the event, and preferably also well formed http-URLs pointing "  # noqa: E501
            "to more information about the event."
        )

        result["properties"]["keywords"]["description"] = (
            "The keywords that describe the topic and type of this event."
        )
        result["required"].append("keywords")

        result["properties"]["super_event"]["description"] = (
            "References the aggregate event containing this event."
        )
        result["properties"]["super_event_type"]["description"] = (
            "If the event has sub_events, describes the type of the event. Current options are "  # noqa: E501
            "<code>null</code>, <code>recurring</code>, which means a repeating event, and "  # noqa: E501
            "<code>umbrella</code>, which means a major event that has sub-events."
        )
        result["properties"]["event_status"]["description"] = (
            "As defined in schema.org/Event. Postponed events do not have a date set, "
            "rescheduled events have been moved to different date."
        )
        result["properties"]["type_id"]["description"] = (
            "Event type. Current options are General (Event), Course and Volunteering."
        )

        result["properties"]["publication_status"]["description"] = (
            "Specifies whether the event should be published in the API (<code>public</code>) or "  # noqa: E501
            "not (<code>draft</code>)."
        )
        result["required"].append("publication_status")

        result["properties"]["data_source"]["description"] = (
            "Unique identifier (URI)for the system from which this event came from, preferably "  # noqa: E501
            "URL with more information about the system and its policies."
        )
        result["properties"]["publisher"]["description"] = (
            "Id of the organization that published this event in Linked events."
        )
        result["properties"]["sub_events"]["description"] = (
            "For aggregate events this contains references to all sub events. Usually this "  # noqa: E501
            "means that the sub events are part of series. The field <code>super_event_type</code> "  # noqa: E501
            "tells the type of the aggregate event."
        )
        result["properties"]["in_language"]["description"] = (
            "The languages spoken or supported at the event."
        )
        result["properties"]["audience"]["description"] = (
            "The audience groups (picked from keywords) this event is intended for."
        )
        result["properties"]["created_time"]["description"] = (
            "Time when the event was created."
        )
        result["properties"]["last_modified_time"]["description"] = (
            "Time when the event was last modified."
        )
        result["properties"]["created_by"]["description"] = (
            "URL reference to the user that created this event (user endpoint)."
        )
        result["properties"]["last_modified_by"]["description"] = (
            "URL reference to the user that last modified this event (user endpoint)."
        )
        result["properties"]["date_published"]["description"] = (
            "Date this event is free to be published."
        )

        result["properties"]["start_time"]["description"] = "Time the event will start."
        result["required"].append("start_time")

        result["properties"]["end_time"]["description"] = "Time the event will end."
        result["properties"]["user_name"]["description"] = "Name of the external user."
        result["properties"]["user_email"]["description"] = (
            "Email of the external user."
        )
        result["properties"]["user_phone_number"]["description"] = (
            "Phone number of the external user."
        )
        result["properties"]["user_organization"]["description"] = (
            "Organization of the external user."
        )
        result["properties"]["user_consent"]["description"] = (
            "Consent to user information of the external user."
        )
        result["properties"]["environment"]["description"] = (
            "Environment of the event. Current options are in (Indoor) and out (Outdoor)."  # noqa: E501
        )
        result["properties"]["environmental_certificate"]["description"] = (
            "Url of the environmental certificate."
        )
        result["properties"]["audience_min_age"]["description"] = (
            "Minimum age of attendees."
        )
        result["properties"]["audience_max_age"]["description"] = (
            "Maximum age of attendees."
        )
        result["properties"]["deleted"]["description"] = (
            "Whether this event has been deleted in the original data source."
        )
        result["properties"]["maximum_attendee_capacity"]["description"] = (
            "Maximum number of people allowed to enrol to the event. Can also be an estimate of "  # noqa: E501
            "the maximum number of attendees."
        )
        result["properties"]["minimum_attendee_capacity"]["description"] = (
            "Minimum number of people required to enrol to the event."
        )
        result["properties"]["enrolment_start_time"]["description"] = (
            "Time when enrolment for the event will start."
        )
        result["properties"]["enrolment_end_time"]["description"] = (
            "Time when enrolment for the event will end."
        )

        result["properties"]["custom_data"] = get_custom_data_schema()

        result["properties"]["name"] = {
            "type": "object",
            "properties": {
                lang: {
                    "type": "string",
                    "maxLength": Event.name.field.max_length,
                }
                for lang in get_fixed_lang_codes()
            },
            "description": (
                "Short descriptive name for the event, recommended limit 80 characters."
            ),
        }
        result["required"].append("name")

        result["properties"]["short_description"] = {
            "type": "object",
            "properties": {
                lang: {
                    "type": "string",
                }
                for lang in get_fixed_lang_codes()
            },
            "description": (
                "Short description for the event, recommended limit 140 characters."
            ),
        }

        result["properties"]["description"] = {
            "type": "object",
            "properties": {
                lang: {
                    "type": "string",
                }
                for lang in get_fixed_lang_codes()
            },
            "description": "Long description for the event, several chapters",
        }

        result["properties"]["location_extra_info"] = {
            "type": "object",
            "properties": {
                lang: {
                    "type": "string",
                    "maxLength": Event.location_extra_info.field.max_length,
                }
                for lang in get_fixed_lang_codes()
            },
            "description": (
                'Unstructured extra info about location (like "eastern door of railway station").'  # noqa: E501
            ),
        }

        result["properties"]["provider"] = {
            "type": "object",
            "properties": {
                lang: {
                    "type": "string",
                    "maxLength": Event.provider.field.max_length,
                }
                for lang in get_fixed_lang_codes()
            },
            "description": (
                "Description of who is responsible for the practical implementation of the event."  # noqa: E501
            ),
        }

        result["properties"]["provider_contact_info"] = {
            "type": "object",
            "properties": {
                lang: {
                    "type": "string",
                    "maxLength": Event.provider_contact_info.field.max_length,
                }
                for lang in get_fixed_lang_codes()
            },
            "description": "Provider's contact information, multilingual.",
        }

        result["properties"]["info_url"] = {
            "type": "object",
            "properties": {
                lang: {
                    "type": "string",
                    "format": "uri",
                    "maxLength": Event.info_url.field.max_length,
                }
                for lang in get_fixed_lang_codes()
            },
            "description": "Link (URL) to a page with more information about event.",
        }

        result["required"].append("location")

        return result


class EventLinkSerializerExtension(OpenApiSerializerExtension):
    target_class = EventLinkSerializer

    def map_serializer(self, auto_schema, direction):
        result = super().map_serializer(auto_schema, direction)

        result["description"] = (
            "Links to entities that the event publisher considers related to this event. Eg. "  # noqa: E501
            "links to catering service available during theatrical production. The links will "  # noqa: E501
            "most likely point to unstructured content, ie. web pages suitable for human viewing."  # noqa: E501
        )

        result["properties"]["name"]["description"] = (
            "Name describing contents of the link."
        )
        result["properties"]["link"]["description"] = (
            "Link to an external related entity."
        )
        result["properties"]["language"]["description"] = (
            "Language of the content behind the link."
        )

        return result


class ImageSerializerExtension(OpenApiSerializerExtension):
    target_class = ImageSerializer

    def map_serializer(self, auto_schema, direction):
        result = super().map_serializer(auto_schema, direction)

        result["description"] = (
            "Images are used as pictures for events, places and organizers."
        )

        result["properties"]["id"]["description"] = "Identifier of the image."
        result["properties"]["license"]["description"] = (
            'License data for the image. May be "cc_by" (default) or "event_only". The latter '  # noqa: E501
            "license restricts use of the image and is specified on the API front page."
        )
        result["properties"]["created_time"]["description"] = (
            "Time when the image was created."
        )
        result["properties"]["last_modified_time"]["description"] = (
            "Time when the image was last modified."
        )
        result["properties"]["created_by"]["description"] = (
            "URL reference to the user that created this image (user endpoint)."
        )
        result["properties"]["last_modified_by"]["description"] = (
            "URL reference to the user that last modified this image (user endpoint)."
        )
        result["properties"]["name"]["description"] = "Image description."

        result["properties"]["url"]["description"] = "The image file URL."
        result["required"].append("url")

        result["properties"]["cropping"]["description"] = "Cropping data for the image."
        result["properties"]["photographer_name"]["description"] = (
            "Name of the photographer."
        )
        result["properties"]["data_source"]["description"] = (
            "Identifies the source for data, this is specific to API provider. This is useful "  # noqa: E501
            "for API users, as any data quality issues are likely to be specific to data source "  # noqa: E501
            "and workarounds can be applied as such."
        )
        result["properties"]["publisher"]["description"] = (
            "The organization responsible for the image."
        )

        result["properties"]["alt_text"] = {
            "type": "object",
            "properties": {
                lang: {
                    "type": "string",
                    "maxLength": Image.alt_text.field.max_length,
                }
                for lang in get_fixed_lang_codes()
            },
            "description": "The image alt text, multilingual.",
        }

        return result


class KeywordSerializerExtension(OpenApiSerializerExtension):
    target_class = KeywordSerializer

    def map_serializer(self, auto_schema, direction):
        result = super().map_serializer(auto_schema, direction)

        result["description"] = (
            "Keywords are used to describe events. Linked events uses namespaced keywords in "  # noqa: E501
            "order to support having events from different sources. Namespaces are needed because "  # noqa: E501
            "keywords are defined by the organization sourcing the events and can therefore "  # noqa: E501
            "overlap in meaning. Conversely the meaning of same keyword can vary between "  # noqa: E501
            "organizations. Organization sourcing the keyword can be identified by data_source "  # noqa: E501
            "field. Data_source field will later specify standardized namespaces as well."  # noqa: E501
        )

        result["properties"]["id"]["description"] = (
            "Consists of source prefix and source specific identifier. These should be URIs "  # noqa: E501
            "uniquely identifying the keyword, and preferably also well formed http-URLs "  # noqa: E501
            "pointing to more information about the keyword."
        )
        result["properties"]["origin_id"]["description"] = (
            "Identifier for the keyword in the organization using this keyword. For "
            "standardized namespaces this will be a shared identifier."
        )

        result["properties"]["alt_labels"]["description"] = (
            "Alternative labels for this keyword, no language specified."
        )
        result["required"].remove("alt_labels")

        result["properties"]["created_time"]["description"] = (
            "Time when the keyword was created"
        )
        result["properties"]["last_modified_time"]["description"] = (
            "Time when the keyword was last modified"
        )
        result["properties"]["created_by"]["description"] = (
            "URL reference to the user that created this keyword (user endpoint)."
        )
        result["properties"]["last_modified_by"]["description"] = (
            "URL reference to the user that last modified this keyword (user endpoint)."
        )
        result["properties"]["aggregate"]["description"] = (
            "This keyword is an combination of several keywords at source."
        )
        result["properties"]["deprecated"]["description"] = (
            "Whether this keyword has been deprecated in the original data source. It may "  # noqa: E501
            "still contain old events linked to it."
        )
        result["properties"]["has_upcoming_events"]["description"] = (
            "Tells if this keyword entry has any upcoming events."
        )
        result["properties"]["n_events"]["description"] = (
            "Amount of events using this keyword entry as a keyword or an audience."
        )
        result["properties"]["image"]["description"] = (
            "Id of the this keyword entry's image."
        )
        result["properties"]["data_source"]["description"] = (
            "Source of the keyword, typically API provider specific identifier. Will also be "  # noqa: E501
            "used to specify standardized namespaces as they are brought into use."
        )
        result["properties"]["publisher"]["description"] = (
            "Id of the organization that has originally published this keyword."
        )

        result["properties"]["name"] = {
            "type": "object",
            "properties": {
                lang: {
                    "type": "string",
                    "maxLength": Keyword.name.field.max_length,
                }
                for lang in get_fixed_lang_codes()
            },
            "description": "Keyword name, multilingual.",
        }
        result["required"].append("name")

        return result


class KeywordSetSerializerExtension(OpenApiSerializerExtension):
    target_class = KeywordSetSerializer

    def map_serializer(self, auto_schema, direction):
        result = super().map_serializer(auto_schema, direction)

        result["description"] = (
            "Keyword sets are used to group keywords together into classification groups. "  # noqa: E501
            "For example, one set of keywords might describe themes used by an event provider "  # noqa: E501
            "and another could be used to describe audience groups."
        )

        result["properties"]["id"]["description"] = (
            "Unique identifier for this keyword set. These should be URIs identifying the "  # noqa: E501
            "source and the keyword set itself, and preferably also well formed http-URLs "  # noqa: E501
            "pointing to more information about the keyword."
        )
        result["properties"]["origin_id"]["description"] = (
            "Identifier for the keyword set in the originating system, if any."
        )
        result["properties"]["usage"]["description"] = (
            "Usage type for this keyword set. These allow UIs to show the set in "
            "appropriate place."
        )
        result["properties"]["created_time"]["description"] = (
            "Time when the keyword set was created."
        )
        result["properties"]["last_modified_time"]["description"] = (
            "Time when the keyword set was last modified."
        )
        result["properties"]["created_by"]["description"] = (
            "URL reference to the user that created this keyword set (user endpoint)."
        )
        result["properties"]["last_modified_by"]["description"] = (
            "URL reference to the user that last modified this keyword set (user endpoint)."  # noqa: E501
        )
        result["properties"]["image"]["description"] = (
            "Id of the this keyword set entry's image."
        )
        result["properties"]["data_source"]["description"] = (
            "Unique identifier (URI)for the system where this keyword set originated, if any."  # noqa: E501
        )
        result["properties"]["organization"]["description"] = (
            "Organization that has defined this keyword set."
        )

        result["properties"]["name"] = {
            "type": "object",
            "properties": {
                lang: {
                    "type": "string",
                    "maxLength": KeywordSet.name.field.max_length,
                }
                for lang in get_fixed_lang_codes()
            },
            "description": (
                "Name for this keyword set, multilingual. This should be human readable, such "  # noqa: E501
                "that it could be shown as label in UI."
            ),
        }
        result["required"].append("name")

        result["required"].append("keywords")

        return result


class LanguageSerializerExtension(OpenApiSerializerExtension):
    target_class = LanguageSerializer

    def map_serializer(self, auto_schema, direction):
        result = super().map_serializer(auto_schema, direction)

        result["description"] = (
            "Primary purpose of the language endpoint is to allow users to identify which "  # noqa: E501
            "languages are supported for multilingual fields. It also has translations for the "  # noqa: E501
            "names of the languages."
        )

        result["properties"]["id"]["description"] = (
            "Identifier for the language (typically ISO639-1)."
        )
        result["properties"]["translation_available"]["description"] = (
            "Event data may have translations in the languages which have "
            "<code>translation_available</code> set to <code>true</code>."
        )

        result["properties"]["name"] = {
            "type": "object",
            "properties": {
                lang: {
                    "type": "string",
                    "maxLength": Language.name.field.max_length,
                }
                for lang in get_fixed_lang_codes()
            },
            "description": (
                "Translation for the language name. Properties shown here are examples, it is "  # noqa: E501
                "suggested that every language supported has its name translated to every other "  # noqa: E501
                "language. Users of the API cannot rely on any translations being present."  # noqa: E501
            ),
        }
        result["required"].append("name")

        result["required"].append("service_language")

        return result


class OfferSerializerExtension(OpenApiSerializerExtension):
    target_class = OfferSerializer

    def map_serializer(self, auto_schema, direction):
        result = super().map_serializer(auto_schema, direction)

        result["description"] = (
            "Price information record for an event. The prices are not in a structured format and "  # noqa: E501
            "the format depends on information source. An exception to this is the case of free "  # noqa: E501
            "event. These are indicated using is_free flag, which is searchable."
        )

        result["properties"]["is_free"]["description"] = (
            "Whether the event has an admission fee or not."
        )

        if settings.WEB_STORE_INTEGRATION_ENABLED:
            result["properties"]["offer_price_groups"]["description"] = (
                "Customer group selections with concrete pricing for this offer. Used as initial "  # noqa: E501
                "values for registration customer groups when creating a registration for the event "  # noqa: E501
                "that this offer belongs to. When at least one customer group selection exists, "  # noqa: E501
                "the registration is considered to require a payment."
            )

        result["properties"]["price"] = {
            "type": "object",
            "properties": {
                lang: {
                    "type": "string",
                    "maxLength": Offer.price.field.max_length,
                }
                for lang in get_fixed_lang_codes()
            },
            "description": (
                "Public price information of the event. These are not bare numbers but instead "  # noqa: E501
                "descriptions of the pricing scheme."
            ),
        }
        if "required" not in result:
            result["required"] = []
        result["required"].append("price")

        result["properties"]["info_url"] = {
            "type": "object",
            "properties": {
                lang: {
                    "type": "string",
                    "format": "url",
                    "maxLength": Offer.info_url.field.max_length,
                }
                for lang in get_fixed_lang_codes()
            },
            "description": "Link (URL) to a page with more information about offer.",
        }

        result["properties"]["description"] = {
            "type": "object",
            "properties": {
                lang: {
                    "type": "string",
                }
                for lang in get_fixed_lang_codes()
            },
            "description": "Further description of the pricing.",
        }

        return result


class OrganizationSerializerExtensionMixin:
    def map_serializer(self, auto_schema, direction):
        result = super().map_serializer(auto_schema, direction)

        result["description"] = (
            "Organizations are the entities that publish events and other data."
        )

        result["properties"]["id"]["description"] = (
            "Consists of source prefix and source specific identifier. These should be URIs "  # noqa: E501
            "uniquely identifying the organization, and preferably also well formed http-URLs "  # noqa: E501
            "pointing to more information about the organization."
        )

        result["properties"]["origin_id"]["description"] = (
            "Identifier for the organization in the original data source. For standardized "  # noqa: E501
            "namespaces this will be a shared identifier."
        )

        result["properties"]["data_source"]["description"] = (
            "Source of the organization data, typically API provider specific identifier. "  # noqa: E501
            "Will also be used to specify standardized namespaces as they are brought into use."  # noqa: E501
        )
        result["properties"]["classification"]["description"] = (
            "Id of the organization type."
        )
        result["properties"]["name"]["description"] = "The name of the organization."
        result["properties"]["founding_date"]["description"] = (
            "Time the organization was founded."
        )
        result["properties"]["dissolution_date"]["description"] = (
            "Time the organization was dissolved. If present, the organization no longer exists."  # noqa: E501
        )
        result["properties"]["created_time"]["description"] = (
            "Time when the organization was created."
        )
        result["properties"]["last_modified_time"]["description"] = (
            "Time when the organization was last modified."
        )
        result["properties"]["created_by"]["description"] = (
            "URL reference to the user that created this organization (user endpoint)."
        )
        result["properties"]["last_modified_by"]["description"] = (
            "URL reference to the user that last modified this organization (user endpoint)."  # noqa: E501
        )

        result["properties"]["sub_organizations"] = {
            "type": "array",
            "items": {"type": "string"},
            "description": "The organizations that belong to this organization.",
        }

        result["properties"]["affiliated_organizations"] = {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "The organizations that are affiliated partners to this organization, "
                "but not proper suborganizations."
            ),
        }

        result["properties"]["internal"] = {
            "type": "string",
        }

        result["properties"]["replaced_by"] = {
            "type": "string",
        }

        result["properties"]["has_regular_user"] = {
            "type": "boolean",
            "description": (
                "Whether the organization has non-admin users in addition to admin users."  # noqa: E501
            ),
        }

        result["properties"]["is_affiliated"] = {
            "type": "boolean",
            "description": (
                "Whether the organization is an affiliated organization of the parent, "
                "instead of a proper suborganization"
            ),
        }

        return result


class OrganizationListSerializerExtension(
    OpenApiSerializerExtension, OrganizationSerializerExtensionMixin
):
    target_class = OrganizationListSerializer

    def map_serializer(self, auto_schema, direction):
        result = super().map_serializer(auto_schema, direction)

        result["required"].remove("origin_id")
        result["required"].remove("replaced_by")
        result["required"].remove("sub_organizations")
        result["required"].remove("affiliated_organizations")

        return result


class OrganizationDetailSerializerExtension(
    OpenApiSerializerExtension, OrganizationSerializerExtensionMixin
):
    target_class = OrganizationDetailSerializer


class OrganizationClassSerializerExtension(OpenApiSerializerExtension):
    target_class = OrganizationClassSerializer

    def map_serializer(self, auto_schema, direction):
        result = super().map_serializer(auto_schema, direction)

        result["description"] = (
            "Organization classes are used for organization classification."
        )

        result["properties"]["id"]["description"] = (
            "Consists of source prefix and source specific identifier."
        )
        result["properties"]["name"]["description"] = (
            "The name of the organization class."
        )

        result["properties"]["created_time"]["description"] = (
            "Time when the organization class was created."
        )
        result["required"].append("created_time")

        result["properties"]["last_modified_time"]["description"] = (
            "Time when the organization class was last modified."
        )

        result["properties"]["data_source"]["description"] = (
            "Source of the organization data, typically API provider specific identifier. "  # noqa: E501
            "Will also be used to specify standardized namespaces as they are brought into use."  # noqa: E501
        )
        result["required"].remove("data_source")

        result["required"].remove("origin_id")

        return result


class PlaceSerializerExtension(OpenApiSerializerExtension):
    target_class = PlaceSerializer

    def map_serializer(self, auto_schema, direction):
        result = super().map_serializer(auto_schema, direction)

        result["description"] = (
            "Places describe physical locations for events and means for contacting people "  # noqa: E501
            "responsible for these locations. Place definitions come from organizations "  # noqa: E501
            'publishing events (field "publisher") and can thus have slightly different '  # noqa: E501
            "semantics between places sourced from different organizations."
        )

        result["properties"]["id"]["description"] = (
            "Consists of source prefix and source specific identifier. These should be URIs "  # noqa: E501
            "uniquely identifying the place, and preferably also well formed http-URLs pointing "  # noqa: E501
            "to more information about the place."
        )

        result["properties"]["origin_id"]["description"] = (
            "Place identifier in the originating system. Same as id but without the data "  # noqa: E501
            "source prefix."
        )
        result["required"].append("origin_id")

        result["properties"]["publisher"]["description"] = (
            "Organization that provided the location data"
        )
        result["properties"]["created_time"]["description"] = (
            "Time when the place was created"
        )
        result["properties"]["last_modified_time"]["description"] = (
            "Time when the place was last modified"
        )
        result["properties"]["created_by"]["description"] = (
            "URL reference to the user that created this place (user endpoint)."
        )
        result["properties"]["last_modified_by"]["description"] = (
            "URL reference to the user that last modified this place (user endpoint)."
        )
        result["properties"]["email"]["description"] = (
            "Contact email for the place, note that this is not multilingual."
        )
        result["properties"]["address_region"]["description"] = (
            "Larger region for address (like states), not typically used in Finland."
        )
        result["properties"]["postal_code"]["description"] = (
            "Postal code of the location (as used by traditional mail)."
        )
        result["properties"]["post_office_box_num"]["description"] = (
            "PO box for traditional mail, in case mail is not delivered to the building."  # noqa: E501
        )
        result["properties"]["address_country"]["description"] = (
            "Country for the place, not multilingual."
        )
        result["properties"]["deleted"]["description"] = (
            "This place entry is not used anymore, but old events still reference it. This might "  # noqa: E501
            "be because of duplicate removal."
        )
        result["properties"]["has_upcoming_events"]["description"] = (
            "Tells if this place entry has any upcoming events."
        )
        result["properties"]["n_events"]["description"] = (
            "Amount of events using this place entry as location."
        )
        result["properties"]["image"]["description"] = (
            "Id of the this place entry's image."
        )

        result["properties"]["custom_data"] = get_custom_data_schema()

        result["properties"]["position"] = {
            "type": "object",
            "properties": {
                "coordinates": {
                    "type": "array",
                    "items": {"type": "number"},
                    "description": "Coordinates in format specified by type property",
                },
                "type": {
                    "type": "string",
                    "enum": ["Point"],
                    "description": (
                        "Interpretation of the coordinates property. Only point is supported in "  # noqa: E501
                        "this version"
                    ),
                },
            },
            "description": (
                "Geographic position of the place specified using subset of GeoJSON"
            ),
        }

        result["properties"]["name"] = {
            "type": "object",
            "properties": {
                lang: {
                    "type": "string",
                    "maxLength": Place.name.field.max_length,
                }
                for lang in get_fixed_lang_codes()
            },
            "description": "Name of the place, multilingual",
        }
        result["required"].append("name")

        result["properties"]["street_address"] = {
            "type": "object",
            "properties": {
                lang: {
                    "type": "string",
                    "maxLength": Place.street_address.field.max_length,
                }
                for lang in get_fixed_lang_codes()
            },
            "description": "Street address for the place, multilingual",
        }

        result["properties"]["info_url"] = {
            "type": "object",
            "properties": {
                lang: {
                    "type": "string",
                    "format": "url",
                    "maxLength": Place.info_url.field.max_length,
                }
                for lang in get_fixed_lang_codes()
            },
            "description": "Link (URL) to a page with more information about place",
        }

        result["properties"]["description"] = {
            "type": "object",
            "properties": {
                lang: {
                    "type": "string",
                }
                for lang in get_fixed_lang_codes()
            },
            "description": "Short description of the place, multilingual.",
        }

        result["properties"]["address_locality"] = {
            "type": "object",
            "properties": {
                lang: {
                    "type": "string",
                    "maxLength": Place.address_locality.field.max_length,
                }
                for lang in get_fixed_lang_codes()
            },
            "description": (
                "Describes where the address is located, typically this would be name of the city."  # noqa: E501
            ),
        }

        result["properties"]["telephone"] = {
            "type": "object",
            "properties": {
                lang: {
                    "type": "string",
                    "maxLength": Place.telephone.field.max_length,
                }
                for lang in get_fixed_lang_codes()
            },
            "description": "Contact phone number for the place, multilingual",
        }

        result["required"].append("data_source")
        result["required"].remove("divisions")

        return result


class VideoSerializerExtension(OpenApiSerializerExtension):
    target_class = VideoSerializer

    def map_serializer(self, auto_schema, direction):
        result = super().map_serializer(auto_schema, direction)

        result["description"] = (
            "Links to videos that the event publisher considers related to this event."
        )

        result["properties"]["name"]["description"] = (
            "Name describing contents of the video."
        )
        result["properties"]["url"]["description"] = "URL to the video."
        result["properties"]["alt_text"]["description"] = "The video alt text."

        return result
