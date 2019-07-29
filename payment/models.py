from django.db import models
from phonenumber_field.modelfields import PhoneNumberField
import uuid


class Customer(models.Model):
    name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = PhoneNumberField()

    def __str__(self):
        return self.name


class Payment(models.Model):
    STATE_OPEN = "O"
    STATE_PAID = "P"
    STATES = (
        (STATE_OPEN, "Opened"),
        (STATE_PAID, "Paid"),
    )

    ENVIRONMENT_TEST = "T"
    ENVIRONMENT_LIVE = "L"
    ENVIRONMENTS = (
        (ENVIRONMENT_TEST, "Test"),
        (ENVIRONMENT_LIVE, "Live"),
    )

    id = models.CharField(max_length=255, primary_key=True, default=uuid.uuid4)
    timestamp = models.DateTimeField(auto_now_add=True)
    state = models.CharField(max_length=1, choices=STATES)
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True)
    environment = models.CharField(max_length=1, choices=ENVIRONMENTS, default=ENVIRONMENT_TEST)

    def __str__(self):
        return self.id


class PaymentItem(models.Model):
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE)
    item_type = models.CharField(max_length=255)
    item_data = models.TextField()
    title = models.CharField(max_length=255)
    price = models.DecimalField(decimal_places=2, max_digits=10)

    def __str__(self):
        return f"{self.payment.id}: {self.title}"
