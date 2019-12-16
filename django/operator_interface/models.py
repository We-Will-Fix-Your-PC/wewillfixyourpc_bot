from django.db import models
from django.utils import timezone
import json
from django.contrib.auth.models import User


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='userprofile')
    picture = models.ImageField()
    fb_persona_id = models.CharField(max_length=255, blank=True, null=True)


class NotificationSubscription(models.Model):
    subscription_info = models.TextField()
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    @property
    def subscription_info_json(self):
        return json.loads(self.subscription_info)

    @subscription_info_json.setter
    def subscription_info_json(self, value):
        self.subscription_info = json.dumps(value)


class Conversation(models.Model):
    FACEBOOK = "FB"
    TWITTER = "TW"
    TELEGRAM = "TG"
    AZURE = "AZ"
    GOOGLE_ACTIONS = "GA"
    PLATFORM_CHOICES = (
        (FACEBOOK, "Facebook"),
        (TWITTER, "Twitter"),
        (TELEGRAM, "Telegram"),
        (AZURE, "Azure"),
        (GOOGLE_ACTIONS, "Actions on Google"),
    )

    platform = models.CharField(max_length=2, choices=PLATFORM_CHOICES)
    platform_id = models.CharField(max_length=255)
    agent_responding = models.BooleanField(default=True)
    current_agent = models.ForeignKey(
        User, blank=True, null=True, default=None, on_delete=models.SET_DEFAULT
    )
    conversation_user_id = models.UUIDField(blank=True, null=True)
    conversation_name = models.CharField(max_length=255, blank=True, null=True)
    conversation_pic = models.ImageField(blank=True, null=True)

    additional_conversation_data = models.TextField(blank=True, null=True)

    def __str__(self):
        platform = list(filter(lambda p: p[0] == self.platform, self.PLATFORM_CHOICES))
        platform = platform[0][1] if len(platform) else "UNKNOWN"
        return f"{platform} - {self.conversation_name}"

    @classmethod
    def get_or_create_conversation(
        cls, platform, platform_id, conversation_name=None, conversation_pic=None, agent_responding=True
    ):
        try:
            conv = cls.objects.get(platform=platform, platform_id=platform_id)
            if conversation_name is not None:
                conv.conversation_name = conversation_name
            if conversation_pic is not None:
                conv.conversation_pic = conversation_pic
            conv.save()
            return conv
        except cls.DoesNotExist:
            conv = cls(
                platform=platform,
                platform_id=platform_id,
                conversation_name=conversation_name,
                conversation_pic=conversation_pic,
                agent_responding=agent_responding
            )
            conv.save()
            return conv

    def reset(self):
        self.agent_responding = True
        self.save()


class ConversationRating(models.Model):
    sender_id = models.CharField(max_length=255)
    time = models.DateTimeField(auto_now_add=True)
    rating = models.PositiveSmallIntegerField()

    def __str__(self):
        return str(self.sender_id)


class Message(models.Model):
    TO_CUSTOMER = "I"
    FROM_CUSTOMER = "O"
    DIRECTION_CHOICES = ((TO_CUSTOMER, "To customer"), (FROM_CUSTOMER, "From customer"))

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    message_id = models.CharField(max_length=255)
    direction = models.CharField(max_length=1, choices=DIRECTION_CHOICES)
    text = models.TextField(blank=True, default="")
    timestamp = models.DateTimeField(default=timezone.now)
    user = models.ForeignKey(User, blank=True, null=True, on_delete=models.SET_NULL)
    read = models.BooleanField(default=False)
    delivered = models.BooleanField(default=False)
    image = models.URLField(blank=True, null=True)
    payment_request = models.UUIDField(blank=True, null=True)
    payment_confirm = models.UUIDField(blank=True, null=True)
    card = models.TextField(blank=True, null=True)
    selection = models.TextField(blank=True, null=True)
    request = models.CharField(max_length=255, null=True, blank=True)
    guessed_intent = models.CharField(max_length=255, null=True, blank=True)
    end = models.BooleanField(default=False, null=True)

    class Meta:
        ordering = ("timestamp",)

    def __str__(self):
        return f"{str(self.conversation)} - {self.timestamp.isoformat()}"

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

    def __str__(self):
        return self.suggested_response


class MessageEntity(models.Model):
    message = models.ForeignKey(Message, on_delete=models.CASCADE)
    entity = models.CharField(max_length=255)
    value = models.TextField()

    def __str__(self):
        return self.entity
