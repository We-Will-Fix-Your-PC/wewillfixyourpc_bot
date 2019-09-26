# (generated with --quick)

import operator_interface.models
from typing import Any, Tuple, Type

BaseUserAdmin: Any
ConversationRatingAdmin: Any
User: Any
admin: module
models: module

class UserAdmin(Any):
    inlines: Tuple[Type[UserProfileInline]]

class UserProfileInline(Any):
    can_delete: bool
    model: Type[operator_interface.models.UserProfile]
    verbose_name_plural: str
