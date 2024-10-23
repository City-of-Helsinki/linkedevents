import django_filters
from django.db.models import Q, Value
from django.db.models.functions import Concat
from django.utils.functional import cached_property
from django.utils.translation import gettext as _
from rest_framework.exceptions import PermissionDenied as DRFPermissionDenied
from rest_framework.exceptions import ValidationError

from registrations.models import PriceGroup, Registration, SignUp, SignUpGroup
from registrations.utils import has_allowed_substitute_user_email_domain


class ActionDependingBackend(django_filters.rest_framework.DjangoFilterBackend):
    def get_filterset_kwargs(self, request, queryset, view):
        kwargs = super().get_filterset_kwargs(request, queryset, view)
        kwargs["action"] = view.action

        return kwargs


class ActionDependingFilter(django_filters.rest_framework.FilterSet):
    def __init__(self, *args, **kwargs):
        self.action = kwargs.pop("action", None)
        super().__init__(*args, **kwargs)


class SignUpBaseFilter(ActionDependingFilter):
    @cached_property
    def _user_admin_organizations(self):
        return self.request.user.get_admin_organizations_and_descendants()

    @cached_property
    def _user_registration_admin_organizations(self):
        return self.request.user.get_registration_admin_organizations_and_descendants()

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)

        user = self.request.user

        if self.action and self.action != "list" or user.is_superuser:
            return queryset

        # By default, return only signups of registrations to which
        # user has admin rights or is registration user who is
        # strongly identified.
        qs_filter = Q(
            registration__event__publisher__in=self._user_registration_admin_organizations
        ) | (
            Q(registration__event__publisher__in=self._user_admin_organizations)
            & Q(registration__created_by=user)
        )

        if has_allowed_substitute_user_email_domain(user.email):
            qs_filter |= Q(
                registration__registration_user_accesses__email=user.email,
                registration__registration_user_accesses__is_substitute_user=True,
            )

        if user.is_strongly_identified:
            qs_filter |= Q(registration__registration_user_accesses__email=user.email)

        return queryset.filter(qs_filter)

    def filter_registration(self, queryset, name, value: list[str]):
        user = self.request.user

        try:
            registrations = Registration.objects.filter(pk__in=value)
        except ValueError:
            raise ValidationError(
                {"registration": _("Invalid registration ID(s) given.")}
            )

        if not registrations:
            return self.Meta.model.objects.none()

        if user.is_superuser:
            return queryset.filter(registration__in=registrations)

        qs_filter = Q(
            event__publisher__in=self._user_registration_admin_organizations
        ) | (
            Q(event__publisher__in=self._user_admin_organizations) & Q(created_by=user)
        )

        if has_allowed_substitute_user_email_domain(user.email):
            qs_filter |= Q(
                registration_user_accesses__email=user.email,
                registration_user_accesses__is_substitute_user=True,
            )

        if user.is_strongly_identified:
            qs_filter |= Q(registration_user_accesses__email=user.email)

        registrations = registrations.filter(qs_filter)

        if not registrations:
            raise DRFPermissionDenied(
                _(
                    "Only the admins of the registration organizations have access rights."  # noqa: E501
                )
            )

        return queryset.filter(registration__in=registrations)

    @staticmethod
    def _build_text_annotations(relation_accessor=""):
        return {
            f"{relation_accessor}first_last_name": Concat(
                f"{relation_accessor}first_name",
                Value(" "),
                f"{relation_accessor}last_name",
            ),
            f"{relation_accessor}last_first_name": Concat(
                f"{relation_accessor}last_name",
                Value(" "),
                f"{relation_accessor}first_name",
            ),
        }

    @staticmethod
    def _build_text_filter(text_param, relation_accessor=""):
        filters = {
            f"{relation_accessor}first_last_name__icontains": text_param,
            f"{relation_accessor}last_first_name__icontains": text_param,
            "contact_person__email__icontains": text_param,
            "contact_person__membership_number__icontains": text_param,
            "contact_person__phone_number__icontains": text_param,
        }

        q_set = Q()
        for item in filters.items():
            q_set |= Q(item)

        return q_set

    def filter_text(self, queryset, name, value):
        return queryset.annotate(**self._build_text_annotations()).filter(
            self._build_text_filter(value)
        )


class SignUpFilter(SignUpBaseFilter):
    registration = django_filters.Filter(
        widget=django_filters.widgets.CSVWidget(),
        method="filter_registration",
        help_text=_(
            "Search for signups with the given registration as specified by id. "
            "Multiple ids are separated by comma."
        ),
    )

    attendee_status = django_filters.MultipleChoiceFilter(
        choices=SignUp.ATTENDEE_STATUSES,
        widget=django_filters.widgets.CSVWidget(),
        help_text=_(
            "Search for signups with the given attendee status. "
            "Multiple types are separated by comma."
        ),
    )

    text = django_filters.CharFilter(
        method="filter_text",
        help_text=_(
            "Search (case insensitive) through the text fields of a signup (first_name, last_name) "  # noqa: E501
            "and the signup's contact person (email, membership_number and phone_number)."  # noqa: E501
        ),
    )

    class Meta:
        model = SignUp
        fields = ("registration", "attendee_status")


class SignUpGroupFilter(SignUpBaseFilter):
    registration = django_filters.Filter(
        widget=django_filters.widgets.CSVWidget(),
        method="filter_registration",
        help_text=_(
            "Search for signup groups with the given registration as specified by id. "
            "Multiple ids are separated by comma."
        ),
    )

    attendee_status = django_filters.MultipleChoiceFilter(
        field_name="signups__attendee_status",
        choices=SignUp.ATTENDEE_STATUSES,
        widget=django_filters.widgets.CSVWidget(),
        help_text=_(
            "Search for signup groups with the given attendee status. "
            "Multiple types are separated by comma."
        ),
    )

    text = django_filters.CharFilter(
        method="filter_text",
        help_text=_(
            "Search (case insensitive) through the text fields of signups (first_name, last_name) "  # noqa: E501
            "and the contact person (email, membership_number and phone_number) in a signup group."  # noqa: E501
        ),
    )

    def filter_text(self, queryset, name, value):
        return queryset.annotate(
            **self._build_text_annotations(relation_accessor="signups__")
        ).filter(self._build_text_filter(value, relation_accessor="signups__"))

    class Meta:
        model = SignUpGroup
        fields = ("registration",)


class PriceGroupFilter(ActionDependingFilter):
    publisher = django_filters.Filter(
        widget=django_filters.widgets.CSVWidget(),
        method="filter_publisher",
        help_text=_(
            "Search for customer groups belonging to an organization as specified by id. "  # noqa: E501
            "Multiple ids are separated by comma. Use the value <code>none</code> for "
            "default customer groups."
        ),
    )

    description = django_filters.CharFilter(
        lookup_expr="icontains",
        help_text=_(
            "Search (case insensitive) through customer groups' multilingual description field."  # noqa: E501
        ),
    )

    is_free = django_filters.BooleanFilter(
        widget=django_filters.widgets.BooleanWidget(),
        help_text=_(
            "Search for customer groups that are free of charge or that have a price."
        ),
    )

    def filter_publisher(self, queryset, name, value: list[str]):
        empty_ids = ("None", "none")

        publisher_ids = [
            publisher_id for publisher_id in value if publisher_id not in empty_ids
        ]

        qs_filter = Q(publisher_id__in=publisher_ids)
        if any([empty_id in value for empty_id in empty_ids]):
            qs_filter |= Q(publisher=None)

        return queryset.filter(qs_filter)

    class Meta:
        model = PriceGroup
        fields = ("publisher", "description", "is_free")
