from django.db import models
from django.utils import timezone
import json
import uuid
import datetime
import django_keycloak_auth.users
import keycloak.exceptions
import re
from django.db.models import Count
from django.contrib.auth.models import User
from django.db.models import Q


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
        if not self.conversation_user_id:
            return self.conversation_name if self.conversation_name else "Unknown"
        try:
            user = django_keycloak_auth.users.get_user_by_id(
                self.conversation_user_id
            ).user
        except keycloak.exceptions.KeycloakClientError as e:
            return self.conversation_name if self.conversation_name else "Unknown"
        return f"{user.get('firstName')} {user.get('lastName')}"

    def last_platform(self):
        messages = Message.objects.filter(platform__conversation=self)
        last_message = messages.order_by("-timestamp").first()
        if last_message is None:
            return None
        return last_message.platform

    def last_usable_platform(self, tag=None, alert=False, text=None):
        platforms = (
            self.conversationplatform_set.annotate(page_count=Count("messages"))
            .filter(page_count__gte=1)
            .order_by("-messages__timestamp")
        )
        for platform in platforms:
            if platform.can_message(tag, alert, text):
                return platform
        return None

    def update_user_id(self, user_id):
        if user_id == self.conversation_user_id:
            return self
        other_conversation = Conversation.objects.filter(Q(conversation_user_id=user_id), ~Q(id=self.id))
        if len(other_conversation) > 0:
            for platform in self.conversationplatform_set.all():
                platform.conversation = other_conversation[0]
                platform.save()
            other_conversation[0].current_agent = self.current_agent
            other_conversation[0].agent_responding = self.agent_responding
            other_conversation[0].save()
            self.delete()
            return other_conversation[0]
        else:
            self.conversation_user_id = user_id
            self.save()
            return self

    def can_message(self, tag=None, alert=False, text=None):
        return any([p.can_message(tag, alert, text) for p in self.conversationplatform_set.all()])

    def is_typing(self):
        return any([p.is_typing for p in self.conversationplatform_set.all()])


class ConversationPlatform(models.Model):
    FACEBOOK = "FB"
    TWITTER = "TW"
    TELEGRAM = "TG"
    AZURE = "AZ"
    GOOGLE_ACTIONS = "GA"
    SMS = "TX"
    CHAT = "CH"
    ABC = "AB"
    EMAIL = "EM"
    WHATSAPP = "WA"
    PLATFORM_CHOICES = (
        (FACEBOOK, "Facebook"),
        (TWITTER, "Twitter"),
        (TELEGRAM, "Telegram"),
        (AZURE, "Azure"),
        (GOOGLE_ACTIONS, "Actions on Google"),
        (SMS, "SMS"),
        (CHAT, "Customer chat"),
        (ABC, "Apple Business chat"),
        (EMAIL, "Email"),
        (WHATSAPP, "WhatsApp"),
    )

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE)
    platform = models.CharField(max_length=2, choices=PLATFORM_CHOICES)
    platform_id = models.CharField(max_length=255)
    additional_platform_data = models.TextField(blank=True, null=True)
    is_typing = models.BooleanField(default=False)

    def __str__(self):
        platform = list(filter(lambda p: p[0] == self.platform, self.PLATFORM_CHOICES))
        platform = platform[0][1] if len(platform) else "UNKNOWN"
        return f"{platform} - {self.platform_id}"

    @classmethod
    def exists(cls, platform, platform_id):
        try:
            conv = cls.objects.filter(platform=platform, platform_id=platform_id).first()
            return conv if conv else None
        except cls.DoesNotExist:
            return None

    @classmethod
    def create(cls, platform, platform_id, customer_user_id=None):
        conv = None
        if customer_user_id is not None:
            conv = Conversation.objects.filter(conversation_user_id=customer_user_id).first()
        if conv is None:
            conv = Conversation(conversation_user_id=customer_user_id)
            conv.save()

        plat = cls(platform=platform, platform_id=platform_id, conversation=conv)
        plat.save()
        return plat

    @classmethod
    def is_whatsapp_template(cls, text):
        TEMPLATES = [re.compile(t) for t in [
            r"Your (.+) repair \(ticket #(.+)\) of (.+) is complete and your device is ready to collect at your"
            r" earliest convenience"
        ]]

        return any(t.fullmatch(text) for t in TEMPLATES)

    def can_message(self, tag=None, alert=False, text=None):
        if self.platform == self.FACEBOOK:
            if tag in [
                "CONFIRMED_EVENT_UPDATE",
                "POST_PURCHASE_UPDATE",
                "ACCOUNT_UPDATE",
            ]:
                return True
            elif tag == "HUMAN_AGENT":
                last_message = (
                    self.messages.order_by("-timestamp")
                    .filter(direction=Message.FROM_CUSTOMER)
                    .first()
                )
                if last_message and last_message.timestamp > timezone.now() - datetime.timedelta(
                    days=7
                ):
                    return True
            else:
                last_message = (
                    self.messages.order_by("-timestamp")
                    .filter(direction=Message.FROM_CUSTOMER)
                    .first()
                )
                if last_message and last_message.timestamp > timezone.now() - datetime.timedelta(
                    hours=24
                ):
                    return True
            return False
        elif self.platform == self.WHATSAPP:
            if text and self.is_whatsapp_template(text):
                return True
            else:
                last_message = (
                    self.messages.order_by("-timestamp")
                    .filter(direction=Message.FROM_CUSTOMER)
                    .first()
                )
                if last_message and last_message.timestamp > timezone.now() - datetime.timedelta(
                    hours=24
                ):
                    return True
                else:
                    return False
        elif self.platform == self.GOOGLE_ACTIONS:
            return False
        elif self.platform == self.CHAT and alert:
            # Not really sure about the best way to guarantee the notification got through, so lets just not for now
            # try:
            #     data = json.loads(self.additional_platform_data) \
            #         if self.additional_platform_data else {}
            # except json.JSONDecodeError:
            #     data = {}
            #
            # push = data.get("push", [])
            # return len(push) > 0
            return False
        elif self.platform == self.ABC:
            last_message: Message = self.messages.order_by("-timestamp").filter(
                direction=Message.FROM_CUSTOMER
            ).first()
            if last_message:
                return not last_message.end
            return True
        elif self.platform == self.EMAIL and alert:
            return False
        else:
            return True


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

    SENDING = "S"
    DELIVERED = "D"
    READ = "R"
    FAILED = "F"
    STATES = (
        (SENDING, "Sending"),
        (DELIVERED, "Delivered"),
        (READ, "Read"),
        (FAILED, "Failed"),
    )

    platform = models.ForeignKey(
        ConversationPlatform, on_delete=models.CASCADE, related_name="messages"
    )
    message_id = models.UUIDField(default=uuid.uuid4)
    platform_message_id = models.CharField(max_length=255, blank=True, null=True)
    direction = models.CharField(max_length=1, choices=DIRECTION_CHOICES)
    text = models.TextField(blank=True, default="")
    timestamp = models.DateTimeField(default=timezone.now)
    user = models.ForeignKey(User, blank=True, null=True, on_delete=models.SET_NULL)
    state = models.CharField(max_length=1, choices=STATES, default=SENDING)
    image = models.URLField(blank=True, null=True)
    payment_request = models.UUIDField(blank=True, null=True)
    payment_confirm = models.UUIDField(blank=True, null=True)
    card = models.TextField(blank=True, null=True)
    selection = models.TextField(blank=True, null=True)
    request = models.CharField(max_length=255, null=True, blank=True)
    guessed_intent = models.CharField(max_length=255, null=True, blank=True)
    end = models.BooleanField(default=False, null=True)
    reply_to = models.ForeignKey("self", on_delete=models.SET_NULL, related_name="replies", blank=True, null=True)
    reaction = models.CharField(blank=True, null=True, max_length=5)

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
