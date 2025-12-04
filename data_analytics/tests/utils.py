from collections.abc import Callable

from rest_framework import status
from rest_framework.test import APIClient


def assert_objects_in_response_data(object_pks: list[str | int], data: list[dict]):
    response_object_ids = {obj["id"] for obj in data}
    expected_object_ids = {obj_pk for obj_pk in object_pks}

    assert response_object_ids == expected_object_ids


def get_detail_and_assert_object_in_response(
    api_client: APIClient, get_detail_func: Callable, object_pk: str | int
):
    response = get_detail_func(api_client, object_pk)

    assert response.status_code == status.HTTP_200_OK
    assert_objects_in_response_data([object_pk], [response.data])

    return response


def get_list_and_assert_objects_in_response(
    api_client: APIClient,
    get_list_func: Callable,
    object_pks: list[str | int],
    query: str | None = None,
):
    if query:
        response = get_list_func(api_client, query=query)
    else:
        response = get_list_func(api_client)

    assert response.status_code == status.HTTP_200_OK
    assert_objects_in_response_data(object_pks, response.data["data"])

    return response
