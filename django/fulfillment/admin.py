from django.contrib import admin
from djsingleton.admin import SingletonAdmin
from . import models


class NetworkAlternativeNameInline(admin.TabularInline):
    model = models.NetworkAlternativeName


@admin.register(models.Network)
class NetworkAdmin(admin.ModelAdmin):
    inlines = [NetworkAlternativeNameInline]


admin.site.register(models.ContactDetails, SingletonAdmin)
admin.site.register(models.OpeningHours)
admin.site.register(models.OpeningHoursOverride)
admin.site.register(models.RepairType)
admin.site.register(models.Repair)
admin.site.register(models.Brand)
admin.site.register(models.Model)
admin.site.register(models.PhoneUnlock)
