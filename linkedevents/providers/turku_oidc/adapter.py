from helusers.adapter import SocialAccountAdapter as HelSocialAccountAdapter
from helusers.user_utils import update_user
from helusers.utils import username_to_uuid

from helevents.models import User



class SocialAccountAdapter(HelSocialAccountAdapter):
    def pre_social_login(self, request, sociallogin):
        """Update user based on token information."""
        user = sociallogin.user

        # If the user hasn't been saved yet, it will be updated
        # later on in the sign-up flow.
        if not user.pk:
            try:
                user = User.objects.get(uuid=username_to_uuid(user.username))
                sociallogin.connect(request, user)                  # We have to connect the user if we want to login from django || respa admin using tunnistamo
            except User.DoesNotExist:
                return
        data = sociallogin.account.extra_data
        oidc = sociallogin.account.provider == 'turku_oidc'
        update_user(user, data, oidc)