from django.db import models
from operator_interface.models import ConversationPlatform
import uuid


class AccountLinkingState(models.Model):
    id = models.UUIDField(unique=True, primary_key=True, default=uuid.uuid4)
    conversation = models.ForeignKey(
        ConversationPlatform,
        on_delete=models.CASCADE,
        related_name="sms_account_linking_state",
    )
    timestamp = models.DateTimeField(auto_now_add=True)
