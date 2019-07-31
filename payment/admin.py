from django.contrib import admin
from . import models


@admin.register(models.PaymentToken)
class PaymentTokenAdmin(admin.ModelAdmin):
    readonly_fields = ('token',)


admin.site.register(models.Customer)
admin.site.register(models.Payment)
admin.site.register(models.PaymentItem)
