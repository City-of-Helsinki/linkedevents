from django.db import models
from knox.models import AuthToken


class DataAnalyticsAuthToken(AuthToken):
    name = models.CharField(max_length=255, unique=True)

    objects = models.Manager()

    def __str__(self):
        return self.name
