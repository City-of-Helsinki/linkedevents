from django.conf import settings

from helusers.tunnistamo_oidc import TunnistamoOIDCAuth as HelusersTunnistamoOIDCAuth


class TunnistamoOIDCAuth(HelusersTunnistamoOIDCAuth):
    name = 'tunnistamo'
    OIDC_ENDPOINT = '%s/openid' % getattr(settings, 'OIDC_API_TOKEN_AUTH')['ISSUER']
    END_SESSION_URL = ''

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.OIDC_ENDPOINT = self.setting('OIDC_ENDPOINT', self.OIDC_ENDPOINT)