from django.contrib import admin
from . import models


class UtteranceResponseInline(admin.StackedInline):
    model = models.UtteranceResponse


class UtteranceButtonInline(admin.StackedInline):
    model = models.UtteranceButton


@admin.register(models.Utterance)
class AdminUtterance(admin.ModelAdmin):
    inlines = [UtteranceResponseInline, UtteranceButtonInline]
    ordering = ('name',)


admin.site.register(models.EnvironmentModel)
admin.site.register(models.TestingUser)
