from django.db import models
from djsingleton.models import SingletonModel
from operator_interface.models import Conversation
import uuid


class Config(SingletonModel):
    auth = models.TextField(blank=True, null=True)
    bearer_token = models.CharField(max_length=255, blank=True, null=True)


class AccountLinkingState(models.Model):
    id = models.UUIDField(unique=True, primary_key=True, default=uuid.uuid4)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)
