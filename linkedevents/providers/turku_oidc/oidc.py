from helusers.oidc import resolve_user, ApiTokenAuthentication as HelusersApiTokenAuthentication
from helusers.authz import UserAuthorization

from rest_framework.exceptions import AuthenticationFailed
from django.utils.translation import ugettext as _

class ApiTokenAuthentication(HelusersApiTokenAuthentication):
    def authenticate(self, request):
        jwt_value = self.get_jwt_value(request)
        if jwt_value is None:
            return None
        try:
            payload = self.decode_jwt(jwt_value)
        except:
            return None
        self.validate_claims(payload)
        user_resolver = self.settings.USER_RESOLVER  # Default: resolve_user
        user = user_resolver(request, payload)
        auth = UserAuthorization(user, payload, self.settings)

        if self.settings.REQUIRE_API_SCOPE_FOR_AUTHENTICATION:
            api_scope = self.settings.API_SCOPE_PREFIX
            if not auth.has_api_scope_with_prefix(api_scope):
                raise AuthenticationFailed(
                    _("Not authorized for API scope \"{api_scope}\"")
                    .format(api_scope=api_scope))
        return (user, auth)