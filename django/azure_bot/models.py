from django.db import models


class AccessToken(models.Model):
    token = models.TextField()
    expires_at = models.DateTimeField()
