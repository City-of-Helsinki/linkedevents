from allauth.socialaccount import providers
from helusers.providers.helsinki_oidc.provider import HelsinkiOIDCAccount, HelsinkiOIDCProvider



class TurkuOIDCAccount(HelsinkiOIDCAccount):
    pass


class TurkuOIDCProvider(HelsinkiOIDCProvider):
    id = 'turku_oidc'
    name = 'City of Turku employees (OIDC)'
    package = 'linkedevents.providers.turku_oidc'
    account_class = TurkuOIDCAccount


providers.registry.register(TurkuOIDCProvider)