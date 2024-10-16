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
            "Registration-specific reservation code value from the SeatsReservation object."
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

        result["properties"]["subject"]["description"] = "Subject of the email."

        result["properties"]["body"]["description"] = "Body of the email."
        result["properties"]["body"]["example"] = "<p>Email message body</p>"

        result["properties"]["signup_groups"]["description"] = (
            "Ids of attendees whose contact persons will receive the email message."
        )
        result["properties"]["signup_groups"]["example"] = [1]

        result["properties"]["signups"]["description"] = (
            "Ids of signup groups whose contact persons will receive the email message."
        )
        result["properties"]["signups"]["example"] = [1]

        return result


class OfferPriceGroupSerializerExtension(OpenApiSerializerExtension):
    target_class = OfferPriceGroupSerializer

    def map_serializer(self, auto_schema, direction):
        result = super().map_serializer(auto_schema, direction)

        result["description"] = (
            "Customer group selection with concrete pricing for an event's price offer. Used as "
            "initial values for registration customer groups when creating a registration for "
            "the event that the offer belongs to."
        )

        result["properties"]["id"]["description"] = (
            "Unique identifier for this offer customer group."
        )
        result["properties"]["price_group"]["description"] = (
            "The organization-level customer group whose instance this offer customer group is. "
            "Gives the name / label for the offer customer group and determines if the "
            "customer group is free. Price will be forced to 0 if the customer group is free."
        )
        result["properties"]["price"]["description"] = (
            "Price of this customer group including VAT."
        )
        result["properties"]["vat_percentage"]["description"] = (
            "VAT percentage of this customer group. Possible values are %(vat_values)s."
        ) % {
            "vat_values": ", ".join(
                [f"<code>{vat[0]}</code>" for vat in VAT_PERCENTAGES]
            )
        }
        result["properties"]["price_without_vat"]["description"] = (
            "Price of this customer group excluding VAT. Calculated automatically based on "
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
            "Customer group selection for an organization. Used for creating customer groups "
            "with prices for events and registrations. Default customer groups are available to "
            "all organizations."
        )

        result["properties"]["id"]["description"] = (
            "Unique identifier for this customer group."
        )
        result["properties"]["publisher"]["description"] = (
            "Unique identifier of the organization to which this customer group belongs to. "
            "Default customer group will have a <code>null</code> value here."
        )
        result["properties"]["is_free"]["description"] = (
            "Determines if the customer group is free of charge or if it should have a price once "
            "it is used in registration customer group selections."
        )
        result["properties"]["created_time"]["description"] = (
            "Time when this customer group was created."
        )
        result["properties"]["last_modified_time"]["description"] = (
            "Time when this customer group was last modified."
        )
        result["properties"]["created_by"]["description"] = (
            "URL reference to the user that created this customer group (user endpoint)."
        )
        result["properties"]["last_modified_by"]["description"] = (
            "URL reference to the user that last modified this customer group (user endpoint)."
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
            "Registrations are used for event registrations. They allow users to sign up to events."
        )

        result["properties"]["id"]["description"] = (
            "Unique identifier for this registration."
        )
        result["properties"]["current_attendee_count"]["description"] = (
            "The number of attendees registered for the event."
        )
        result["properties"]["current_waiting_list_count"]["description"] = (
            "The number of attendees on the waiting list for the event."
        )

        result["properties"]["remaining_attendee_capacity"]["description"] = (
            "The number of seats remaining in the event. Returns <code>null</code> if attendee "
            "capacity is not limited."
        )
        result["required"].remove("remaining_attendee_capacity")

        result["properties"]["remaining_waiting_list_capacity"]["description"] = (
            "The number of seats remaining in the waiting list. Returns <code>null</code> if "
            "waiting list capacity is not limited."
        )
        result["required"].remove("remaining_waiting_list_capacity")

        result["properties"]["signups"]["description"] = (
            "The list of attendees in the registration. Only admin users of the publisher "
            "organization are allowed to see this information."
        )
        result["required"].remove("signups")

        result["properties"]["data_source"]["description"] = (
            "Identifies the source for data, this is specific to API provider. This value is "
            "inherited from the event of the registration."
        )
        result["properties"]["publisher"]["description"] = (
            "Id for the organization that published this registration. This value is inherited "
            "from the event of the registration."
        )
        result["properties"]["created_time"]["description"] = (
            "Time when this registration was created."
        )
        result["properties"]["last_modified_time"]["description"] = (
            "Time when this registration was last modified."
        )
        result["properties"]["created_by"]["description"] = (
            "URL reference to the user that created this registration (user endpoint)."
        )
        result["properties"]["last_modified_by"]["description"] = (
            "URL reference to the user that last modified this registration (user endpoint)."
        )
        result["properties"]["audience_min_age"]["description"] = (
            "Minimum age of attendees."
        )
        result["properties"]["audience_max_age"]["description"] = (
            "Maximum age of attendees."
        )
        result["properties"]["enrolment_start_time"]["description"] = (
            "Time when enrolment for the event starts."
        )
        result["properties"]["enrolment_end_time"]["description"] = (
            "Time when enrolment for the event ends."
        )
        result["properties"]["maximum_attendee_capacity"]["description"] = (
            "Maximum number of attendees allowed for the event. Can also be an estimate of the "
            "maximum number of attendees."
        )
        result["properties"]["minimum_attendee_capacity"]["description"] = (
            "Minimum number of attendees required for the event to take place."
        )
        result["properties"]["waiting_list_capacity"]["description"] = (
            "Maximum number of people allowed to register to the waiting list."
        )
        result["properties"]["maximum_group_size"]["description"] = (
            "Maximum number of attendees allowed in a single group."
        )
        result["properties"]["mandatory_fields"]["description"] = (
            "Mandatory fields in the enrolment form."
        )
        result["properties"]["registration_user_accesses"]["description"] = (
            "Registration user accesses are used to define registration specific permissions."
        )

        if settings.WEB_STORE_INTEGRATION_ENABLED:
            result["properties"]["registration_price_groups"]["description"] = (
                "Customer group selections that should be available when signing up to this "
                "registration. When at least one customer group selection exists, the registration "
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

        result["description"] = (
            "Customer group selection with concrete pricing for a registration."
        )

        result["properties"]["id"]["description"] = (
            "Unique identifier for this registration customer group."
        )
        result["properties"]["price_group"]["description"] = (
            "The organization-level customer group whose instance this registration customer "
            "group is. Gives the name / label for the registration customer group and determines "
            "if the customer group is free. Price will be forced to 0 if the customer group is "
            "free."
        )
        result["properties"]["price"]["description"] = (
            "Price of this customer group including VAT."
        )
        result["properties"]["vat_percentage"]["description"] = (
            "VAT percentage of this customer group. Possible values are %(vat_values)s."
        ) % {
            "vat_values": ", ".join(
                [f"<code>{vat[0]}</code>" for vat in VAT_PERCENTAGES]
            )
        }
        result["properties"]["price_without_vat"]["description"] = (
            "Price of this customer group excluding VAT. Calculated automatically based on "
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
            "List of email addresses which has registration specific permissions. Substitute "
            "user permissions are also given through a registration user access."
        )

        result["properties"]["id"]["description"] = (
            "Unique identifier for this registration user access."
        )
        result["properties"]["email"]["description"] = (
            "Email address of the registration user. Unique per registration. Must end with one "
            "of the allowed domain names if <code>is_substitute_user<code> is set to "
            '<code>true</code> (by default, only "hel.fi" domain is allowed).'
        )

        result["properties"]["language"]["description"] = (
            "The registration user's service language that should be used in invitation emails."
        )
        result["properties"]["language"]["example"] = "fi"

        result["properties"]["is_substitute_user"]["description"] = (
            "Determines if the registration user is a substitute user for the creator of the "
            "registration. A substitute user has full administration rights for the registration. "
            "The registration user's email must end with an allowed domain name to be able to set "
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
        result["properties"]["seats"]["description"] = "The number of reserved seats."

        result["properties"]["code"]["description"] = (
            "Reservation code which is used when signing to the registration."
        )
        result["properties"]["code"]["example"] = "d380965a-52ad-4e75-be6f-6588454697b7"

        result["properties"]["timestamp"]["description"] = (
            "Time when the reservation was created."
        )
        result["properties"]["timestamp"]["example"] = "2024-06-13T07:29:25.880792Z"

        result["properties"]["expiration"]["description"] = (
            "Time when the reservation expires."
        )
        result["properties"]["expiration"]["example"] = "2024-06-13T07:29:25.880792Z"

        result["properties"]["in_waitlist"]["description"] = (
            "Tells if the seats are reserved to the waitlist."
        )

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
            "Signups are used as attendees for registrations. An attendee can have their own "
            "contact person information if they are not part of a group."
        )

        result["properties"]["id"]["description"] = (
            "Unique identifier for this attendee."
        )
        result["properties"]["first_name"]["description"] = "Attendee's first name"
        result["properties"]["last_name"]["description"] = "Attendee's last name."
        result["properties"]["date_of_birth"]["description"] = (
            "Attendee's date of birth."
        )
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
            'Event presence status of the attendee. Options are "present" and "not_present".'
        )
        result["properties"]["registration"]["description"] = (
            "Id of the registration to which this signup is related."
        )
        result["properties"]["created_time"]["description"] = (
            "Time when this signup was created."
        )
        result["properties"]["last_modified_time"]["description"] = (
            "Time when this signup was last modified."
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

        result["description"] = (
            "Provides contact information for an attendee or an attendee group. In case of a "
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

        result["properties"]["service_language"]["description"] = (
            "Contact person's service language."
        )
        result["properties"]["service_language"]["example"] = "fi"

        result["properties"]["membership_number"]["description"] = (
            "Contact person's membership number."
        )

        result["properties"]["notifications"]["description"] = (
            "Methods to send notifications to the contact person. Options are "
            "%(notification_options)s."
        ) % {
            "notification_options": ", ".join(
                [f"<code>{option[0]}</code>" for option in NOTIFICATION_TYPES]
            )
        }
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
            "URL reference to the user that last modified this signup group (user endpoint)."
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
            "Customer group selection for an attendee. Determines the price of the signup."
        )

        result["properties"]["registration_price_group"]["description"] = (
            "ID of one of the registration's available customer group selections."
        )

        return result


class SignUpPaymentSerializerExtension(OpenApiSerializerExtension):
    target_class = SignUpPaymentSerializer

    def map_serializer(self, auto_schema, direction):
        result = super().map_serializer(auto_schema, direction)

        result["description"] = (
            "A payment created for a signup or a signup group using the web store integration. "
            "A signup is confirmed only when the payment is paid."
        )

        result["properties"]["id"]["description"] = (
            "Unique identifier for this payment."
        )
        result["properties"]["external_order_id"]["description"] = (
            "Unique identified for this payment in the Talpa web store. Returned by the web "
            "store after the payment has been successfully created."
        )
        result["properties"]["checkout_url"]["description"] = (
            "URL to Talpa web store's checkout UI. Does not require the user to be logged in. "
            "The payment can be paid using either checkout_url or logged_in_checkout_url."
        )
        result["properties"]["logged_in_checkout_url"]["description"] = (
            "URL to Talpa web store's checkout UI. Requires the user to be logged in. The "
            "payment can be paid using either checkout_url or logged_in_checkout_url."
        )
        result["properties"]["amount"]["description"] = (
            "Amount of the payment with VAT included."
        )
        result["properties"]["status"]["description"] = (
            "Status of the payment. Possible values are %(payment_statuses)s."
        ) % {
            "payment_statuses": ", ".join(
                [
                    f"<code>{status[0]}</code>"
                    for status in SignUpPayment.PAYMENT_STATUSES
                ]
            )
        }
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
