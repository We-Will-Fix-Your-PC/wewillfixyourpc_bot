from django.db import models
from djsingleton.models import SingletonModel


class Config(SingletonModel):
    auth = models.TextField(blank=True, null=True)
    bearer_token = models.CharField(max_length=255, blank=True, null=True)
