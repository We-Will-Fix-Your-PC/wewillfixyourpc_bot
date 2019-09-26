# (generated with --quick)

from typing import Any

PhoneNumberField: Any
SingletonModel: Any
models: module
uuid: module

class Brand(Any):
    display_name: Any
    name: Any
    def __str__(self) -> Any: ...

class ContactDetails(Any):
    Meta: type
    email: Any
    maps_link: Any
    phone_number: Any
    def __str__(self) -> str: ...

class Model(Any):
    brand: Any
    display_name: Any
    name: Any
    def __str__(self) -> Any: ...

class Network(Any):
    display_name: Any
    name: Any
    def __str__(self) -> Any: ...

class NetworkAlternativeName(Any):
    display_name: Any
    name: Any
    network: Any
    def __str__(self) -> Any: ...

class OpeningHours(Any):
    Meta: type
    close: Any
    friday: Any
    monday: Any
    open: Any
    saturday: Any
    sunday: Any
    thursday: Any
    tuesday: Any
    wednesday: Any
    def __str__(self) -> str: ...

class OpeningHoursOverride(Any):
    close: Any
    closed: Any
    day: Any
    open: Any
    def __str__(self) -> Any: ...

class PhoneUnlock(Any):
    brand: Any
    device: Any
    device_name: Any
    network: Any
    price: Any
    time: Any
    def __str__(self) -> str: ...

class Repair(Any):
    device: Any
    price: Any
    repair: Any
    repair_time: Any
    def __str__(self) -> str: ...

class RepairType(Any):
    display_name: Any
    name: Any
    def __str__(self) -> Any: ...

class UnlockForm(Any):
    email: Any
    id: Any
    name: Any
    network_name: Any
    phone_unlock: Any
