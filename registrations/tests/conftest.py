from django.utils import translation

from events.tests.conftest import *  # noqa
from linkedevents.tests.conftest import *  # noqa
from registrations.models import SignUp


@pytest.fixture(autouse=True)
def use_english():
    with translation.override("en"):
        yield


@pytest.fixture
def signup(registration):
    return SignUp.objects.create(
        registration=registration,
        email="test@test.com",
    )


@pytest.fixture
def signup2(registration):
    return SignUp.objects.create(
        registration=registration,
        email="test2@test.com",
    )


@pytest.fixture
def signup3(registration):
    return SignUp.objects.create(
        registration=registration,
        email="test3@test.com",
    )
