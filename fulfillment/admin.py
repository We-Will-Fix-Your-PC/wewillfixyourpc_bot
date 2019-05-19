from django.contrib import admin
from djsingleton.admin import SingletonAdmin
from . import models

admin.site.register(models.ContactDetails, SingletonAdmin)
admin.site.register(models.OpeningHours)
admin.site.register(models.OpeningHoursOverride)
