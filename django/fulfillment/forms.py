from django import forms
from django.core.validators import ValidationError
from phonenumber_field.formfields import PhoneNumberField


def validate_imei(value):
    def luhn_checksum(number):
        def digits_of(n):
            return [int(d) for d in str(n)]

        digits = digits_of(number)
        odd_digits = digits[-1::-2]
        even_digits = digits[-2::-2]
        checksum = 0
        checksum += sum(odd_digits)
        for d in even_digits:
            checksum += sum(digits_of(d * 2))
        return checksum % 10

    try:
        checksum = luhn_checksum(value)
    except ValueError:
        checksum = 1

    if checksum or len(str(value)) != 15:
        raise ValidationError("Invalid IMEI")


class IMEIField(forms.CharField):
    default_validators = [validate_imei]

3
class UnlockForm(forms.Form):
    name = forms.CharField(label='Your name', max_length=255)
    email = forms.EmailField(label='Your email', max_length=255)
    phone = PhoneNumberField(label='Your current phone number')
    imei = IMEIField(label="The phone's IMEI (this can be found by dialing *#06#)", max_length=15)
