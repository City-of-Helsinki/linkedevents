from decimal import Decimal

import factory

from events.tests.factories import EventFactory, OfferFactory, OrganizationFactory
from registrations.enums import VatPercentage
from registrations.models import (
    OfferPriceGroup,
    PriceGroup,
    Registration,
    RegistrationPriceGroup,
    RegistrationUserAccess,
    SeatReservationCode,
    SignUp,
    SignUpContactPerson,
    SignUpGroup,
    SignUpGroupProtectedData,
    SignUpPayment,
    SignUpPriceGroup,
    SignUpProtectedData,
    WebStoreMerchant,
)


class RegistrationFactory(factory.django.DjangoModelFactory):
    event = factory.SubFactory(EventFactory)

    class Meta:
        model = Registration


class RegistrationUserAccessFactory(factory.django.DjangoModelFactory):
    registration = factory.SubFactory(RegistrationFactory)

    class Meta:
        model = RegistrationUserAccess


class SignUpGroupFactory(factory.django.DjangoModelFactory):
    registration = factory.SubFactory(RegistrationFactory)

    class Meta:
        model = SignUpGroup


class SignUpFactory(factory.django.DjangoModelFactory):
    registration = factory.SubFactory(RegistrationFactory)

    class Meta:
        model = SignUp


class SignUpContactPersonFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SignUpContactPerson


class SignUpGroupProtectedDataFactory(factory.django.DjangoModelFactory):
    registration = factory.SubFactory(RegistrationFactory)
    signup_group = factory.SubFactory(SignUpGroupFactory)

    class Meta:
        model = SignUpGroupProtectedData


class SignUpProtectedDataFactory(factory.django.DjangoModelFactory):
    registration = factory.SubFactory(RegistrationFactory)
    signup = factory.SubFactory(SignUpFactory)

    class Meta:
        model = SignUpProtectedData


class SeatReservationCodeFactory(factory.django.DjangoModelFactory):
    registration = factory.SubFactory(RegistrationFactory)

    class Meta:
        model = SeatReservationCode


class PriceGroupFactory(factory.django.DjangoModelFactory):
    publisher = factory.SubFactory(OrganizationFactory)
    description_fi = factory.Sequence(lambda n: "FI Price Group {0}".format(n))
    description_sv = factory.Sequence(lambda n: "SV Price Group {0}".format(n))
    description_en = factory.Sequence(lambda n: "EN Price Group {0}".format(n))

    class Meta:
        model = PriceGroup


class RegistrationPriceGroupFactory(factory.django.DjangoModelFactory):
    registration = factory.SubFactory(RegistrationFactory)
    price_group = factory.SubFactory(PriceGroupFactory)
    price = Decimal("10")
    vat_percentage = VatPercentage.VAT_24.value

    class Meta:
        model = RegistrationPriceGroup


class OfferPriceGroupFactory(factory.django.DjangoModelFactory):
    offer = factory.SubFactory(OfferFactory)
    price_group = factory.SubFactory(PriceGroupFactory)
    price = Decimal("10")
    vat_percentage = VatPercentage.VAT_24.value

    class Meta:
        model = OfferPriceGroup


class SignUpPriceGroupFactory(factory.django.DjangoModelFactory):
    signup = factory.SubFactory(SignUpFactory)

    @factory.lazy_attribute
    def registration_price_group(self):
        return RegistrationPriceGroupFactory(
            registration=self.signup.registration,
            price_group__publisher=self.signup.publisher,
        )

    @factory.lazy_attribute
    def description_fi(self):
        return self.registration_price_group.price_group.description_fi

    @factory.lazy_attribute
    def description_sv(self):
        return self.registration_price_group.price_group.description_sv

    @factory.lazy_attribute
    def description_en(self):
        return self.registration_price_group.price_group.description_en

    @factory.lazy_attribute
    def price(self):
        return self.registration_price_group.price

    @factory.lazy_attribute
    def vat_percentage(self):
        return self.registration_price_group.vat_percentage

    @factory.lazy_attribute
    def price_without_vat(self):
        return self.registration_price_group.price_without_vat

    @factory.lazy_attribute
    def vat(self):
        return self.registration_price_group.vat

    class Meta:
        model = SignUpPriceGroup


class SignUpPaymentFactory(factory.django.DjangoModelFactory):
    signup = factory.SubFactory(SignUpFactory)
    amount = Decimal("10")

    class Meta:
        model = SignUpPayment


class WebStoreMerchantFactory(factory.django.DjangoModelFactory):
    organization = factory.SubFactory(OrganizationFactory)

    name = factory.Sequence(lambda n: "Merchant {0}".format(n))
    street_address = factory.Faker("street_address", locale="fi_FI")
    zipcode = factory.Faker("postcode", locale="fi_FI")
    city = factory.Faker("city", locale="fi_FI")
    email = factory.Faker("email")
    phone_number = factory.Faker("phone_number", locale="fi_FI")
    url = factory.Faker("url")
    terms_of_service_url = factory.Faker("url")
    business_id = factory.Faker("company_business_id", locale="fi_FI")

    paytrail_merchant_id = factory.Sequence(lambda n: "{0}".format(n))

    class Meta:
        model = WebStoreMerchant
