from rest_framework import status

from events.tests.utils import versioned_reverse as reverse


def create_signup(api_client, registration_pk, signup_data):
    # Reserve seats
    reservation_url = reverse(
        "registration-reserve-seats", kwargs={"pk": registration_pk}
    )
    seat_reservation_data = {"seats": 1, "waitlist": True}
    response = api_client.post(reservation_url, seat_reservation_data, format="json")
    assert response.status_code == status.HTTP_201_CREATED

    # Sign up
    create_url = reverse(
        "registration-signup-list",
        kwargs={"pk": registration_pk},
    )
    signup_payload = {
        "reservation_code": response.data["code"],
        "signups": [signup_data],
    }

    response = api_client.post(create_url, signup_payload, format="json")
    return response


def assert_create_signup(api_client, registration_pk, signup_data):
    response = create_signup(api_client, registration_pk, signup_data)
    assert response.status_code == status.HTTP_201_CREATED

    return response
