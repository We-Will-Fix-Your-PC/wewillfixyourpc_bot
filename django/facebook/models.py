from django.db import models
import uuid


class AccountLinkingState(models.Model):
    id = models.UUIDField(unique=True, primary_key=True, default=uuid.uuid4)
    user_id = models.UUIDField()
    timestamp = models.DateTimeField(auto_now_add=True)
