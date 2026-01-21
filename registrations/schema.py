from django.conf import settings
from drf_spectacular.extensions import OpenApiSerializerExtension

from linkedevents.utils import get_fixed_lang_codes
from registrations.models import VAT_PERCENTAGES, PriceGroup, SignUpPayment
from registrations.notifications import NOTIFICATION_TYPES, NotificationType
from registrations.serializers import (
    CreateSignUpsSerializer,
    MassEmailSerializer,
    OfferPriceGroupSerializer,
    PriceGroupSerializer,
    RegistrationPriceGroupSerializer,
    RegistrationUserAccessSerializer,
    SeatReservationCodeSerializer,
    SignUpContactPersonSerializer,
    SignUpGroupCreateSerializer,
    SignUpGroupSerializer,
    SignUpPaymentSerializer,
    SignUpPriceGroupSerializer,
    SignUpSerializer,
)


class CreateSignUpsSerializerExtension(OpenApiSerializerExtension):
    target_class = CreateSignUpsSerializer

    def map_serializer(self, auto_schema, direction):
        result = super().map_serializer(auto_schema, direction)

        result["description"] = (
            "Payload which is to used to create signups to a registration."
        )

        result["properties"]["reservation_code"]["description"] = (
            "Registration-specific reservation code value from the SeatsReservation object."  # noqa: E501
        )
        result["properties"]["registration"]["description"] = (
            "Id of the registration to which the user is going to signup."
        )
        result["properties"]["signups"]["description"] = (
            "The list of persons to enrol to the registration."
        )

        return result


class MassEmailSerializerExtension(OpenApiSerializerExtension):
    target_class = MassEmailSerializer

    def map_serializer(self, auto_schema, direction):
        result = super().map_serializer(auto_schema, direction)

        result["description"] = "Payload of the send message request."

        result["properties"]["body"]["example"] = "<p>Email message body</p>"

        result["properties"]["signup_groups"]["example"] = [1]

        result["properties"]["signups"]["example"] = [1]

        return result


class OfferPriceGroupSerializerExtension(OpenApiSerializerExtension):
    target_class = OfferPriceGroupSerializer

    def map_serializer(self, auto_schema, direction):
        result = super().map_serializer(auto_schema, direction)

        vat_percentages = ", ".join(
            [f"<code>{vat[0]}</code>" for vat in VAT_PERCENTAGES]
        )

        result["description"] = (
            "Customer group selection with concrete pricing for an event's price offer. Used as "  # noqa: E501
            "initial values for registration customer groups when creating a registration for "  # noqa: E501
            "the event that the offer belongs to."
        )

        result["properties"]["id"]["description"] = (
            "Unique identifier for this offer customer group."
        )
        result["properties"]["price_group"]["description"] = (
            "The organization-level customer group whose instance this offer customer group is. "  # noqa: E501
            "Gives the name / label for the offer customer group and determines if the "
            "customer group is free. Price will be forced to 0 if the customer group is free."  # noqa: E501
        )
        result["properties"]["price"]["description"] = (
            "Price of this customer group including VAT."
        )
        result["properties"]["vat_percentage"]["description"] = (
            f"VAT percentage of this customer group. Possible values are {vat_percentages}."  # noqa: E501
        )
        result["properties"]["price_without_vat"]["description"] = (
            "Price of this customer group excluding VAT. Calculated automatically based on "  # noqa: E501
            "<code>price</code> and <code>vat_percentage</code>."
        )
        result["properties"]["vat"]["description"] = (
            "Amount of VAT. Calculated automatically based on <code>price</code> and "
            "</code>price_without_vat</code>."
        )

        return result


class PriceGroupSerializerExtension(OpenApiSerializerExtension):
    target_class = PriceGroupSerializer

    def map_serializer(self, auto_schema, direction):
        result = super().map_serializer(auto_schema, direction)

        result["description"] = (
            "Customer group selection for an organization. Used for creating customer groups "  # noqa: E501
            "with prices for events and registrations. Default customer groups are available to "  # noqa: E501
            "all organizations."
        )

        result["properties"]["id"]["description"] = (
            "Unique identifier for this customer group."
        )
        result["properties"]["publisher"]["description"] = (
            "Unique identifier of the organization to which this customer group belongs to. "  # noqa: E501
            "Default customer group will have a <code>null</code> value here."
        )
        result["properties"]["is_free"]["description"] = (
            "Determines if the customer group is free of charge or if it should have a price once "  # noqa: E501
            "it is used in registration customer group selections."
        )
        result["properties"]["created_time"]["description"] = (
            "Time when this customer group was created."
        )
        result["properties"]["last_modified_time"]["description"] = (
            "Time when this customer group was last modified."
        )
        result["properties"]["created_by"]["description"] = (
            "URL reference to the user that created this customer group (user endpoint)."  # noqa: E501
        )
        result["properties"]["last_modified_by"]["description"] = (
            "URL reference to the user that last modified this customer group (user endpoint)."  # noqa: E501
        )

        result["properties"]["description"] = {
            "type": "object",
            "properties": {
                lang: {
                    "type": "string",
                    "maxLength": PriceGroup.description.field.max_length,
                }
                for lang in get_fixed_lang_codes()
            },
            "description": "Name or short description of the customer group.",
        }
        result["required"].append("description")

        return result


class RegistrationSerializerExtension(OpenApiSerializerExtension):
    target_class = "registrations.serializers.RegistrationSerializer"

    def map_serializer(self, auto_schema, direction):
        result = super().map_serializer(auto_schema, direction)

        result["description"] = (
            "Registrations are used for event registrations. They allow users to sign up to events."  # noqa: E501
        )

        result["properties"]["id"]["description"] = (
            "Unique identifier for this registration."
        )

        result["required"].remove("remaining_attendee_capacity")
        result["required"].remove("remaining_waiting_list_capacity")
        result["required"].remove("signups")

        result["properties"]["created_by"]["description"] = (
            "URL reference to the user that created this registration (user endpoint)."
        )
        result["properties"]["last_modified_by"]["description"] = (
            "URL reference to the user that last modified this registration (user endpoint)."  # noqa: E501
        )
        result["properties"]["registration_user_accesses"]["description"] = (
            "Registration user accesses are used to define registration specific permissions."  # noqa: E501
        )

        if settings.WEB_STORE_INTEGRATION_ENABLED:
            result["properties"]["registration_price_groups"]["description"] = (
                "Customer group selections that should be available when signing up to this "  # noqa: E501
                "registration. When at least one customer group selection exists, the registration "  # noqa: E501
                "is considered to require a payment."
            )

        fixed_lang_codes = get_fixed_lang_codes()
        result["properties"].update(
            {
                "confirmation_message": {
                    "type": "object",
                    "properties": {
                        lang: {
                            "type": "string",
                        }
                        for lang in fixed_lang_codes
                    },
                },
                "instructions": {
                    "type": "object",
                    "properties": {
                        lang: {
                            "type": "string",
                        }
                        for lang in fixed_lang_codes
                    },
                },
            }
        )

        result["required"].remove("signup_url")

        return result


class RegistrationPriceGroupSerializerExtension(OpenApiSerializerExtension):
    target_class = RegistrationPriceGroupSerializer

    def map_serializer(self, auto_schema, direction):
        result = super().map_serializer(auto_schema, direction)

        vat_percentages = ", ".join(
            [f"<code>{vat[0]}</code>" for vat in VAT_PERCENTAGES]
        )

        result["description"] = (
            "Customer group selection with concrete pricing for a registration."
        )

        result["properties"]["id"]["description"] = (
            "Unique identifier for this registration customer group."
        )
        result["properties"]["price_group"]["description"] = (
            "The organization-level customer group whose instance this registration customer "  # noqa: E501
            "group is. Gives the name / label for the registration customer group and determines "  # noqa: E501
            "if the customer group is free. Price will be forced to 0 if the customer group is "  # noqa: E501
            "free."
        )
        result["properties"]["price"]["description"] = (
            "Price of this customer group including VAT."
        )
        result["properties"]["vat_percentage"]["description"] = (
            f"VAT percentage of this customer group. Possible values are {vat_percentages}."  # noqa: E501
        )
        result["properties"]["price_without_vat"]["description"] = (
            "Price of this customer group excluding VAT. Calculated automatically based on "  # noqa: E501
            "<code>price</code> and <code>vat_percentage</code>."
        )
        result["properties"]["vat"]["description"] = (
            "Amount of VAT. Calculated automatically based on <code>price</code> and "
            "</code>price_without_vat</code>."
        )

        return result


class RegistrationUserAccessSerializerExtension(OpenApiSerializerExtension):
    target_class = RegistrationUserAccessSerializer

    def map_serializer(self, auto_schema, direction):
        result = super().map_serializer(auto_schema, direction)

        result["description"] = (
            "List of email addresses which has registration specific permissions. Substitute "  # noqa: E501
            "user permissions are also given through a registration user access."
        )

        result["properties"]["id"]["description"] = (
            "Unique identifier for this registration user access."
        )
        result["properties"]["email"]["description"] = (
            "Email address of the registration user. Unique per registration. Must end with one "  # noqa: E501
            "of the allowed domain names if <code>is_substitute_user<code> is set to "
            '<code>true</code> (by default, only "hel.fi" domain is allowed).'
        )

        result["properties"]["language"]["description"] = (
            "The registration user's service language that should be used in invitation emails."  # noqa: E501
        )
        result["properties"]["language"]["example"] = "fi"

        result["properties"]["is_substitute_user"]["description"] = (
            "Determines if the registration user is a substitute user for the creator of the "  # noqa: E501
            "registration. A substitute user has full administration rights for the registration. "  # noqa: E501
            "The registration user's email must end with an allowed domain name to be able to set "  # noqa: E501
            'this to <code>true</code>. By default, only "hel.fi" domain is allowed.'
        )

        return result


class SeatReservationCodeSerializerExtension(OpenApiSerializerExtension):
    target_class = SeatReservationCodeSerializer

    def map_serializer(self, auto_schema, direction):
        result = super().map_serializer(auto_schema, direction)

        result["description"] = (
            "Seats reservation are used to reserve seats for a registration."
        )

        result["properties"]["id"]["description"] = (
            "Unique identifier for this seats reservation."
        )
        result["properties"]["registration"]["description"] = (
            "Id of the registration for which the seats are reserved for."
        )

        result["properties"]["code"]["description"] = (
            "Reservation code which is used when signing to the registration."
        )
        result["properties"]["code"]["example"] = "d380965a-52ad-4e75-be6f-6588454697b7"

        result["properties"]["timestamp"]["example"] = "2024-06-13T07:29:25.880792Z"

        result["properties"]["expiration"]["example"] = "2024-06-13T07:29:25.880792Z"

        return result


class SignUpGroupCreateSerializerExtension(OpenApiSerializerExtension):
    target_class = SignUpGroupCreateSerializer

    def map_serializer(self, auto_schema, direction):
        result = super().map_serializer(auto_schema, direction)

        result["description"] = (
            "Payload which is to used to create a signup group to a registration."
        )

        return result


class SignUpSerializerExtension(OpenApiSerializerExtension):
    target_class = SignUpSerializer

    def map_serializer(self, auto_schema, direction):
        result = super().map_serializer(auto_schema, direction)

        result["description"] = (
            "Signups are used as attendees for registrations. An attendee can have their own "  # noqa: E501
            "contact person information if they are not part of a group."
        )

        result["properties"]["first_name"]["description"] = "Attendee's first name"
        result["properties"]["last_name"]["description"] = "Attendee's last name."
        result["properties"]["street_address"]["description"] = (
            "Attendee's street address."
        )
        result["properties"]["zipcode"]["description"] = "Attendee's postal code."
        result["properties"]["city"]["description"] = "Attendee's city."
        result["properties"]["extra_info"]["description"] = (
            "Extra information about the attendee."
        )
        result["properties"]["attendee_status"]["description"] = (
            'Status of the attendee. Options are "attending" and "waitlisted".'
        )
        result["properties"]["presence_status"]["description"] = (
            'Event presence status of the attendee. Options are "present" and "not_present".'  # noqa: E501
        )
        result["properties"]["registration"]["description"] = (
            "Id of the registration to which this signup is related."
        )
        result["properties"]["created_by"]["description"] = (
            "URL reference to the user that created this signup (user endpoint)."
        )
        result["properties"]["last_modified_by"]["description"] = (
            "URL reference to the user that last modified this signup (user endpoint)."
        )

        result["required"].remove("anonymization_time")

        if "payment" in result["required"]:
            result["required"].remove("payment")
        if "payment_refund" in result["required"]:
            result["required"].remove("payment_refund")
        if "payment_cancellation" in result["required"]:
            result["required"].remove("payment_cancellation")

        return result


class SignUpContactPersonSerializerExtension(OpenApiSerializerExtension):
    target_class = SignUpContactPersonSerializer

    def map_serializer(self, auto_schema, direction):
        result = super().map_serializer(auto_schema, direction)

        notifaction_options = ", ".join(
            [f"<code>{option[0]}</code>" for option in NOTIFICATION_TYPES]
        )

        result["description"] = (
            "Provides contact information for an attendee or an attendee group. In case of a "  # noqa: E501
            "group, the information will be shared for the whole group."
        )

        result["properties"]["id"]["description"] = (
            "Unique identifier for this contact person."
        )
        result["properties"]["first_name"]["description"] = (
            "Contact person's first name."
        )
        result["properties"]["last_name"]["description"] = "Contact person's last name."
        result["properties"]["email"]["description"] = "Contact person's email address."

        result["properties"]["phone_number"]["description"] = (
            "Contact person's phone number."
        )
        result["properties"]["phone_number"]["example"] = "+358441234567"

        result["properties"]["native_language"]["description"] = (
            "Contact person's native language."
        )
        result["properties"]["native_language"]["example"] = "fi"

        result["properties"]["service_language"]["example"] = "fi"

        result["properties"]["membership_number"]["description"] = (
            "Contact person's membership number."
        )

        result["properties"]["notifications"]["description"] = (
            "Methods to send notifications to the contact person. Options are "
            f"{notifaction_options}."
        )
        result["properties"]["notifications"]["example"] = NotificationType.SMS_EMAIL

        return result


class SignUpGroupSerializerExtension(OpenApiSerializerExtension):
    target_class = SignUpGroupSerializer

    def map_serializer(self, auto_schema, direction):
        result = super().map_serializer(auto_schema, direction)

        result["description"] = (
            "Signup groups are used as attendee groups for registrations."
        )

        result["properties"]["id"]["description"] = (
            "Unique identifier for this signup group."
        )
        result["properties"]["registration"]["description"] = (
            "Id of the registration to which this signup group is related."
        )
        result["properties"]["signups"]["description"] = (
            "The list of attendees belonging to this signup group."
        )
        result["properties"]["anonymization_time"]["description"] = (
            "Time when the signup group was anonymized."
        )
        result["properties"]["extra_info"]["description"] = (
            "Extra information about the group."
        )
        result["properties"]["created_time"]["description"] = (
            "Time when this signup group was created."
        )
        result["properties"]["last_modified_time"]["description"] = (
            "Time when this signup group was last modified."
        )
        result["properties"]["created_by"]["description"] = (
            "URL reference to the user that created this signup group (user endpoint)."
        )
        result["properties"]["last_modified_by"]["description"] = (
            "URL reference to the user that last modified this signup group (user endpoint)."  # noqa: E501
        )

        result["required"].remove("anonymization_time")

        if "payment" in result["required"]:
            result["required"].remove("payment")
        if "payment_refund" in result["required"]:
            result["required"].remove("payment_refund")
        if "payment_cancellation" in result["required"]:
            result["required"].remove("payment_cancellation")

        return result


class SignUpPriceGroupSerializerExtension(OpenApiSerializerExtension):
    target_class = SignUpPriceGroupSerializer

    def map_serializer(self, auto_schema, direction):
        result = super().map_serializer(auto_schema, direction)

        result["description"] = (
            "Customer group selection for an attendee. Determines the price of the signup."  # noqa: E501
        )

        return result


class SignUpPaymentSerializerExtension(OpenApiSerializerExtension):
    target_class = SignUpPaymentSerializer

    def map_serializer(self, auto_schema, direction):
        result = super().map_serializer(auto_schema, direction)

        payment_statuses = ", ".join(
            [f"<code>{status[0]}</code>" for status in SignUpPayment.PAYMENT_STATUSES]
        )

        result["description"] = (
            "A payment created for a signup or a signup group using the web store integration. "  # noqa: E501
            "A signup is confirmed only when the payment is paid."
        )

        result["properties"]["id"]["description"] = (
            "Unique identifier for this payment."
        )
        result["properties"]["external_order_id"]["description"] = (
            "Unique identified for this payment in the Talpa web store. Returned by the web "  # noqa: E501
            "store after the payment has been successfully created."
        )
        result["properties"]["checkout_url"]["description"] = (
            "URL to Talpa web store's checkout UI. Does not require the user to be logged in. "  # noqa: E501
            "The payment can be paid using either checkout_url or logged_in_checkout_url."  # noqa: E501
        )
        result["properties"]["logged_in_checkout_url"]["description"] = (
            "URL to Talpa web store's checkout UI. Requires the user to be logged in. The "  # noqa: E501
            "payment can be paid using either checkout_url or logged_in_checkout_url."
        )
        result["properties"]["amount"]["description"] = (
            "Amount of the payment with VAT included."
        )
        result["properties"]["status"]["description"] = (
            f"Status of the payment. Possible values are {payment_statuses}."
        )
        result["properties"]["created_time"]["description"] = (
            "Time when this payment was created."
        )
        result["properties"]["last_modified_time"]["description"] = (
            "Time when this payment was last modified."
        )
        result["properties"]["created_by"]["description"] = (
            "URL reference to the user that created this payment (user endpoint)."
        )
        result["properties"]["last_modified_by"]["description"] = (
            "URL reference to the user that last modified this payment (user endpoint)."
        )

        return result
