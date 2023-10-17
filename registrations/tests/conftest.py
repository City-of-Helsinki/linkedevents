from django.utils import translation

from audit_log.tests.conftest import *  # noqa
from events.tests.conftest import *  # noqa
from linkedevents.tests.conftest import *  # noqa
from registrations.models import SignUp


@pytest.fixture(autouse=True)  # noqa: F405
def use_english():
    with translation.override("en"):
        yield


@pytest.fixture  # noqa: F405
def signup(registration):
    return SignUp.objects.create(
        registration=registration,
        email="test@test.com",
    )


@pytest.fixture  # noqa: F405
def signup2(registration):
    return SignUp.objects.create(
        registration=registration,
        email="test2@test.com",
    )


@pytest.fixture  # noqa: F405
def signup3(registration):
    return SignUp.objects.create(
        registration=registration,
        email="test3@test.com",
    )
