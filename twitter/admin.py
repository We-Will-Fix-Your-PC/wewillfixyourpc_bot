from django.contrib import admin
from djsingleton.admin import SingletonAdmin
from . import models
from . import forms


@admin.register(models.Config)
class ConfigAdmin(SingletonAdmin):
    form = forms.TwitterAuthForm
