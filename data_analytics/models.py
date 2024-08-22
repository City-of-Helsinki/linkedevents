from django.contrib.auth import get_user_model
from django.db import models
from knox.models import AbstractAuthToken


class DataAnalyticsApiToken(AbstractAuthToken):
    name = models.CharField(max_length=255, unique=True)
    user = models.ForeignKey(
        get_user_model(),
        null=False,
        blank=False,
        related_name="da_auth_token_set",
        on_delete=models.CASCADE,
    )

    objects = models.Manager()

    def __str__(self):
        return self.name
