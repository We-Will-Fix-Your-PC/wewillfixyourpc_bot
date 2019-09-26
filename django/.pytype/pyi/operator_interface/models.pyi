# (generated with --quick)

from typing import Any, Tuple

PhoneNumberField: Any
User: Any
json: module
models: module
payment: module
timezone: module

class Conversation(Any):
    AZURE: str
    FACEBOOK: str
    GOOGLE_ACTIONS: str
    PLATFORM_CHOICES: Tuple[Tuple[str, str], Tuple[str, str], Tuple[str, str], Tuple[str, str], Tuple[str, str]]
    TELEGRAM: str
    TWITTER: str
    additional_conversation_data: Any
    agent_responding: Any
    conversation_name: Any
    conversation_pic: Any
    conversation_user_id: Any
    current_agent: Any
    platform: Any
    platform_id: Any
    def __str__(self) -> str: ...
    @classmethod
    def get_or_create_conversation(cls, platform, platform_id, conversation_name = ..., conversation_pic = ...) -> Any: ...
    def reset(self) -> None: ...

class ConversationRating(Any):
    rating: Any
    sender_id: Any
    time: Any
    def __str__(self) -> str: ...

class Message(Any):
    DIRECTION_CHOICES: Tuple[Tuple[str, str], Tuple[str, str]]
    FROM_CUSTOMER: str
    Meta: type
    TO_CUSTOMER: str
    card: Any
    conversation: Any
    delivered: Any
    direction: Any
    end: Any
    image: Any
    message_id: Any
    payment_confirm: Any
    payment_request: Any
    read: Any
    request: Any
    text: Any
    timestamp: Any
    user: Any
    def __str__(self) -> str: ...
    @classmethod
    def message_exits(cls, conversation, message_id) -> bool: ...

class MessageSuggestion(Any):
    message: Any
    suggested_response: Any
    def __str__(self) -> Any: ...

class NotificationSubscription(Any):
    subscription_info: Any
    subscription_info_json: Any
    user: Any

class UserProfile(Any):
    fb_persona_id: Any
    picture: Any
    user: Any
