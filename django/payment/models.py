from django.db import models
from phonenumber_field.modelfields import PhoneNumberField
from django.conf import settings
import uuid
import decimal
import secrets


def make_token():
    return secrets.token_hex(32)


class PaymentToken(models.Model):
    name = models.CharField(max_length=255)
    token = models.CharField(
        max_length=255, default=make_token, editable=False, primary_key=True
    )

    def __str__(self):
        return self.name


class Customer(models.Model):
    name = models.CharField(max_length=255)
    email = models.EmailField(blank=True, null=True)
    phone = PhoneNumberField(blank=True, null=True)

    def __str__(self):
        return self.name

    @classmethod
    def find_customer(cls, *args, **kwargs):
        customer = cls.objects.filter(email=kwargs.get("email"))
        if len(customer) > 0:
            customer = customer[0]
            for k, v in kwargs.items():
                setattr(customer, k, v)
            customer.save()
        else:
            customer = cls(*args, **kwargs)
            customer.save()
        return customer


class Payment(models.Model):
    STATE_OPEN = "O"
    STATE_PAID = "P"
    STATE_COMPLETE = "C"
    STATES = (
        (STATE_OPEN, "Opened"),
        (STATE_PAID, "Paid"),
        (STATE_COMPLETE, "Complete"),
    )

    ENVIRONMENT_TEST = "T"
    ENVIRONMENT_LIVE = "L"
    ENVIRONMENTS = ((ENVIRONMENT_TEST, "Test"), (ENVIRONMENT_LIVE, "Live"))

    id = models.CharField(max_length=255, primary_key=True, default=uuid.uuid4)
    timestamp = models.DateTimeField(auto_now_add=True)
    state = models.CharField(max_length=1, choices=STATES)
    customer = models.ForeignKey(
        Customer, on_delete=models.SET_NULL, null=True, blank=True
    )
    environment = models.CharField(
        max_length=1, choices=ENVIRONMENTS, default=settings.DEFAULT_PAYMENT_ENVIRONMENT
    )
    payment_method = models.CharField(max_length=255, blank=True, default="")

    @property
    def total(self):
        total = decimal.Decimal("0.0")
        for item in self.paymentitem_set.all():
            total += item.price * item.quantity
        return total

    @property
    def description(self):
        description = []
        for item in self.paymentitem_set.all():
            description.append(item.title)
        return ", ".join(description)

    def __str__(self):
        return self.id


class PaymentItem(models.Model):
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE)
    item_type = models.CharField(max_length=255)
    item_data = models.TextField()
    title = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(decimal_places=2, max_digits=10)

    def __str__(self):
        return f"{self.payment.id}: {self.title}"


class ThreeDSData(models.Model):
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE)
    oneTime3DsToken = models.TextField()
    redirectURL = models.TextField()
    orderId = models.TextField()
    sessionId = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)
