from django.db import models
import operator_interface.models


class TestingUser(models.Model):
    platform = models.CharField(max_length=2, choices=operator_interface.models.Conversation.PLATFORM_CHOICES)
    platform_id = models.CharField(max_length=255)
    environment = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.platform}, {self.platform_id}"
