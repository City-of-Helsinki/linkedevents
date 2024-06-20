from django.conf import settings
from django.utils.translation import gettext as _
from rest_framework import authentication
from rest_framework.exceptions import AuthenticationFailed


class WebStoreWebhookUser:
    """Dummy user to be used only with WebStoreWebhookAuthentication."""

    @property
    def is_authenticated(self) -> bool:
        return True


class WebStoreWebhookAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        # django converts 'webhook-api-key' to 'HTTP_WEBHOOK_API_KEY' outside runserver
        api_key = request.META.get("webhook-api-key") or request.META.get(
            "HTTP_WEBHOOK_API_KEY"
        )
        if not api_key:
            return None

        if api_key != settings.WEB_STORE_WEBHOOK_API_KEY:
            raise AuthenticationFailed(_("Invalid webhook API key."))

        return WebStoreWebhookUser(), None

    def authenticate_header(self, request):
        return "Webhook authentication failed."
