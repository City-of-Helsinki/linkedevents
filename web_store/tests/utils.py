from unittest.mock import Mock

from requests import RequestException
from rest_framework import status


def get_mock_response(
    status_code=status.HTTP_201_CREATED,
    json_return_value=None,
    exception_json_return_value=None,
):
    response = Mock()

    response.status_code = status_code
    response.json.return_value = json_return_value or {}

    if status.is_client_error(status_code) or status.is_server_error(status_code):
        exception_response_mock = Mock(status_code=status_code)
        exception_response_mock.json.return_value = exception_json_return_value or {}
        response.raise_for_status.side_effect = RequestException(
            response=exception_response_mock
        )

    return response
