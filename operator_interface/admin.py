from django.contrib import admin
from . import models


admin.site.register(models.Conversation)
admin.site.register(models.ConversationRating)
admin.site.register(models.Message)
