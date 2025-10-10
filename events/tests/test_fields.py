from django.http import HttpResponse
from django.test import override_settings
from django.urls import path
from rest_framework import serializers
from rest_framework.test import APIRequestFactory

from events.fields import ProxyURLField


def proxy_test_view(request, pk):
    return HttpResponse()


PROXY_TEST_VIEW = "proxy-test-view"
PROXY_TEST_PATH = "proxy-test-path"


class ProxyTestUrls:
    urlpatterns = [
        path(f"{PROXY_TEST_PATH}/<int:pk>", proxy_test_view, name=PROXY_TEST_VIEW)
    ]


def test_proxy_url_field_deserializing():
    class ProxyURLFieldSerializer(serializers.Serializer):
        url = ProxyURLField(PROXY_TEST_VIEW, {})

    test_url = "https://test.local/"
    serializer = ProxyURLFieldSerializer(data={"url": test_url})
    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["url"] == test_url


def test_proxy_url_field_serializing_normal():
    class ProxyURLFieldSerializer(serializers.Serializer):
        url = ProxyURLField(PROXY_TEST_VIEW, {})

    class TestModel:
        pk = 1
        url = "https://real-url.local"

    serializer = ProxyURLFieldSerializer(TestModel)

    assert serializer.data["url"] == TestModel.url


@override_settings(ROOT_URLCONF=ProxyTestUrls)
def test_proxy_url_field_serializing_proxied():
    class ProxyURLFieldSerializer(serializers.Serializer):
        url = ProxyURLField(PROXY_TEST_VIEW, {})

    class TestModel:
        pk = 1
        url = "https://real-url.local"

    request = APIRequestFactory().get("/test")
    serializer = ProxyURLFieldSerializer(
        TestModel, context={"use_image_proxy": True, "request": request}
    )

    assert (
        serializer.data["url"] == f"http://testserver/{PROXY_TEST_PATH}/{TestModel.pk}"
    )
