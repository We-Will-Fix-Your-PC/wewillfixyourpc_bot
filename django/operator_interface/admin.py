from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from . import models


class UserProfileInline(admin.StackedInline):
    model = models.UserProfile
    can_delete = False
    verbose_name_plural = "User profile"


class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)


@admin.register(models.ConversationRating)
class ConversationRatingAdmin(admin.ModelAdmin):
    readonly_fields = ("time",)


admin.site.unregister(User)
admin.site.register(User, UserAdmin)
admin.site.register(models.Conversation)
admin.site.register(models.ConversationPlatform)
admin.site.register(models.Message)
admin.site.register(models.MessageEntity)
