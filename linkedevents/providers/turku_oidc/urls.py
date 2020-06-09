from allauth.socialaccount.providers.oauth2.urls import default_urlpatterns
from linkedevents.providers.turku_oidc.provider import TurkuOIDCProvider

urlpatterns = default_urlpatterns(TurkuOIDCProvider)