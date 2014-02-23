from django.db import models
import reversion

class Event(models.Model):
    pass

reversion.register(Event)