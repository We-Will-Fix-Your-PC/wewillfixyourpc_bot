from django.db import models
from django.utils import timezone
import secrets


class Conversation(models.Model):
    FACEBOOK = 'FB'
    TWITTER = 'TW'
    PLATFORM_CHOICES = (
        (FACEBOOK, 'Facebook'),
        (TWITTER, 'Twitter')
    )

    platform = models.CharField(max_length=2, choices=PLATFORM_CHOICES)
    platform_id = models.CharField(max_length=255)
    noonce = models.CharField(max_length=255)
    agent_responding = models.BooleanField(default=True)

    def __str__(self):
        platform = list(filter(lambda p: p[0] == self.platform, self.PLATFORM_CHOICES))
        platform = platform[0][1] if len(platform) else "UNKNOWN"
        return f"{platform} - {self.customer_name}"

    @classmethod
    def get_or_create_conversation(cls, platform, platform_id):
        try:
            return cls.objects.get(platform=platform, platform_id=platform_id)
        except cls.DoesNotExist:
            conv = cls(platform=platform, platform_id=platform_id, noonce=secrets.token_urlsafe(10))
            conv.save()
            return conv

    def rest(self):
        self.noonce = secrets.token_urlsafe(10)
        self.agent_responding = True
        self.save()

class Message(models.Model):
    TO_CUSTOMER = 'I'
    FROM_CUSTOMER = 'O'
    DIRECTION_CHOICES = (
        (TO_CUSTOMER, 'To customer'),
        (FROM_CUSTOMER, 'From customer')
    )

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE)
    message_id = models.CharField(max_length=255)
    direction = models.CharField(max_length=1, choices=DIRECTION_CHOICES)
    text = models.TextField()
    timestamp = models.DateTimeField(default=timezone.now)

    @classmethod
    def message_exits(cls, conversation, message_id):
        try:
            cls.objects.get(conversation=conversation, message_id=message_id)
            return True
        except cls.DoesNotExist:
            return False


class MessageSuggestion(models.Model):
    message = models.ForeignKey(Message, on_delete=models.CASCADE)
    suggested_response = models.TextField()
