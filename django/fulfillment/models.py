from django.db import models
from phonenumber_field.modelfields import PhoneNumberField
from djsingleton.models import SingletonModel


class ContactDetails(SingletonModel):
    email = models.EmailField()
    phone_number = PhoneNumberField()
    maps_link = models.URLField()

    class Meta:
        verbose_name_plural = "Contact details"

    def __str__(self):
        return "Contact Details"


class OpeningHours(models.Model):
    monday = models.BooleanField()
    tuesday = models.BooleanField()
    wednesday = models.BooleanField()
    thursday = models.BooleanField()
    friday = models.BooleanField()
    saturday = models.BooleanField()
    sunday = models.BooleanField()

    open = models.TimeField()
    close = models.TimeField()

    class Meta:
        verbose_name_plural = "Opening hours"

    def __str__(self):
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        enabled = [self.monday, self.tuesday, self.wednesday, self.thursday, self.friday, self.saturday, self.sunday]
        days = map(lambda d: d[1], filter(lambda d: enabled[d[0]], enumerate(days)))
        return ", ".join(days)


class OpeningHoursOverride(models.Model):
    day = models.DateField()

    closed = models.BooleanField()
    open = models.TimeField(blank=True, null=True)
    close = models.TimeField(blank=True, null=True)

    def __str__(self):
        return self.day.isoformat()


class IPhoneRepair(models.Model):
    name = models.CharField(max_length=255)
    repair_name = models.CharField(max_length=255)
    price = models.DecimalField(decimal_places=2, max_digits=10)
    repair_time = models.CharField(max_length=255)

    class Meta:
        verbose_name = "iPhone Repair"
        verbose_name_plural = "iPhone Repairs"

    def __str__(self):
        return f"{self.name} {self.repair_name}"


class IPadRepair(models.Model):
    name = models.CharField(max_length=255)
    repair_name = models.CharField(max_length=255)
    price = models.DecimalField(decimal_places=2, max_digits=10)
    repair_time = models.CharField(max_length=255)

    class Meta:
        verbose_name = "iPad Repair"
        verbose_name_plural = "iPad Repairs"

    def __str__(self):
        return f"{self.name} {self.repair_name}"


class Network(models.Model):
    name = models.CharField(max_length=255)
    display_name = models.CharField(max_length=255)

    def __str__(self):
        return self.display_name


class NetworkAlternativeName(models.Model):
    network = models.ForeignKey(Network, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    display_name = models.CharField(max_length=255)

    def __str__(self):
        return self.display_name


class Brand(models.Model):
    name = models.CharField(max_length=255)
    display_name = models.CharField(max_length=255)

    def __str__(self):
        return self.display_name


class PhoneUnlock(models.Model):
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE)
    network = models.ForeignKey(Network, on_delete=models.CASCADE)
    device = models.CharField(max_length=255, blank=True, null=True)
    price = models.DecimalField(decimal_places=2, max_digits=10)
    time = models.CharField(max_length=255)

    @property
    def device_name(self):
        return self.device if self.device else ""

    def __str__(self):
        return f"{self.brand} {self.device_name} on {self.network}"