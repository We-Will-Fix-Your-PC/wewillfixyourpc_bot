from django.db import models
from django.utils import timezone
import json
import uuid
from django.contrib.auth.models import User


class UserProfile(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="userprofile"
    )
    picture = models.ImageField()
    fb_persona_id = models.CharField(max_length=255, blank=True, null=True)

    def save(self, *args, **kwargs):
        if self.pk is not None:
            old = UserProfile.objects.get(pk=self.pk)
            if self.picture.name != old.picture.name:
                self.fb_persona_id = None
        super().save(*args, **kwargs)


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
    agent_responding = models.BooleanField(default=False)
    current_agent = models.ForeignKey(
        User, blank=True, null=True, default=None, on_delete=models.SET_DEFAULT
    )
    conversation_user_id = models.UUIDField(blank=True, null=True)
    conversation_name = models.CharField(max_length=255, blank=True, null=True)
    conversation_pic = models.ImageField(blank=True, null=True)

    def __str__(self):
        return f"{self.conversation_name}"

    def last_platform(self):
        messages = Message.objects.filter(platform__conversation=self)
        last_message = messages.order_by("-timestamp").first()
        if last_message is None:
            return None
        return last_message.platform


class ConversationPlatform(models.Model):
    FACEBOOK = "FB"
    TWITTER = "TW"
    TELEGRAM = "TG"
    AZURE = "AZ"
    GOOGLE_ACTIONS = "GA"
    SMS = "TX"
    PLATFORM_CHOICES = (
        (FACEBOOK, "Facebook"),
        (TWITTER, "Twitter"),
        (TELEGRAM, "Telegram"),
        (AZURE, "Azure"),
        (GOOGLE_ACTIONS, "Actions on Google"),
        (SMS, "SMS")
    )

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE)
    platform = models.CharField(max_length=2, choices=PLATFORM_CHOICES)
    platform_id = models.CharField(max_length=255)
    additional_platform_data = models.TextField(blank=True, null=True)

    def __str__(self):
        platform = list(filter(lambda p: p[0] == self.platform, self.PLATFORM_CHOICES))
        platform = platform[0][1] if len(platform) else "UNKNOWN"
        return f"{platform} - {self.platform_id}"

    @classmethod
    def exists(cls, platform, platform_id):
        try:
            return cls.objects.get(platform=platform, platform_id=platform_id)
        except cls.DoesNotExist:
            return None

    @classmethod
    def create(cls, platform, platform_id, customer_user_id=None):
        conv = None
        if customer_user_id is not None:
            try:
                conv = Conversation.objects.get(customer_user_id=customer_user_id)
            except Conversation.DoesNotExist:
                pass
        if conv is None:
            conv = Conversation(
                customer_user_id=customer_user_id,
            )
            conv.save()

        plat = cls(platform=platform, platform_id=platform_id, conversation=conv)
        plat.save()
        return plat


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

    DELIVERED = "D"
    READ = "R"
    FAILED = "F"
    STATES = (
        (DELIVERED, "Delivered"),
        (READ, "Read"),
        (FAILED, "Failed")
    )

    platform = models.ForeignKey(
        ConversationPlatform, on_delete=models.CASCADE, related_name="messages"
    )
    message_id = models.UUIDField(default=uuid.uuid4)
    platform_message_id = models.CharField(max_length=255)
    direction = models.CharField(max_length=1, choices=DIRECTION_CHOICES)
    text = models.TextField(blank=True, default="")
    timestamp = models.DateTimeField(default=timezone.now)
    user = models.ForeignKey(User, blank=True, null=True, on_delete=models.SET_NULL)
    state = models.CharField(max_length=1, choices=STATES)
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
        return f"{str(self.platform)} - {self.timestamp.isoformat()}"

    @classmethod
    def message_exits(cls, platform, message_id):
        try:
            cls.objects.get(platform=platform, platform_message_id=message_id)
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
