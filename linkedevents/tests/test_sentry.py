import pytest
from sentry_sdk.serializer import global_repr_processors

from events.tests.factories import ApiKeyUserFactory
from helevents.tests.factories import UserFactory


@pytest.mark.django_db
def test_anonymize_user_repr_function():
    assert len(global_repr_processors) == 1

    user = UserFactory()
    user_repr = global_repr_processors[0](user, None)
    assert user_repr == f"<{user.__class__.__name__}: {user.username}>"

    apikey_user = ApiKeyUserFactory()
    apikey_user_repr = global_repr_processors[0](apikey_user, None)
    assert (
        apikey_user_repr
        == f"<{apikey_user.__class__.__name__}: {apikey_user.username}>"
    )

    nonetype_repr = global_repr_processors[0](None, None)
    assert nonetype_repr == NotImplemented
