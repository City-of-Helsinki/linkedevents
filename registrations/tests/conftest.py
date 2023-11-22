from django.utils import translation

from events.tests.conftest import *  # noqa
from linkedevents.tests.conftest import *  # noqa
from registrations.models import SignUp, SignUpContactPerson


@pytest.fixture(autouse=True)  # noqa: F405
def use_english():
    with translation.override("en"):
        yield


@pytest.fixture  # noqa: F405
def signup(registration):
    signup = SignUp.objects.create(registration=registration)
    SignUpContactPerson.objects.create(signup=signup, email="test@test.com")

    return signup


@pytest.fixture  # noqa: F405
def signup2(registration):
    signup = SignUp.objects.create(registration=registration)
    SignUpContactPerson.objects.create(signup=signup, email="test2@test.com")

    return signup


@pytest.fixture  # noqa: F405
def signup3(registration):
    signup = SignUp.objects.create(registration=registration)
    SignUpContactPerson.objects.create(signup=signup, email="test3@test.com")

    return signup
