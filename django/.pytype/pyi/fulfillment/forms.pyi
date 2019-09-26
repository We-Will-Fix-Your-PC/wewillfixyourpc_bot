# (generated with --quick)

from typing import Any, Callable, List

PhoneNumberField: Any
ValidationError: Any
forms: module

class IMEIField(Any):
    default_validators: List[Callable[[Any], Any]]

class UnlockForm(Any):
    email: Any
    imei: IMEIField
    name: Any
    phone: Any

def validate_imei(value) -> None: ...
