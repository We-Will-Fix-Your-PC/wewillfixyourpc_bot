# (generated with --quick)

from typing import Any, Callable, Tuple

PhoneNumberField: Any
decimal: module
models: module
secrets: module
settings: Any
uuid: module

class Customer(Any):
    email: Any
    name: Any
    phone: Any
    def __str__(self) -> Any: ...
    @classmethod
    def find_customer(cls: Callable, *args, **kwargs) -> Any: ...

class Payment(Any):
    ENVIRONMENTS: Tuple[Tuple[str, str], Tuple[str, str]]
    ENVIRONMENT_LIVE: str
    ENVIRONMENT_TEST: str
    STATES: Tuple[Tuple[str, str], Tuple[str, str], Tuple[str, str]]
    STATE_COMPLETE: str
    STATE_OPEN: str
    STATE_PAID: str
    customer: Any
    description: str
    environment: Any
    id: Any
    payment_method: Any
    state: Any
    timestamp: Any
    total: decimal.Decimal
    def __str__(self) -> Any: ...

class PaymentItem(Any):
    item_data: Any
    item_type: Any
    payment: Any
    price: Any
    quantity: Any
    title: Any
    def __str__(self) -> str: ...

class PaymentToken(Any):
    name: Any
    token: Any
    def __str__(self) -> Any: ...

class ThreeDSData(Any):
    oneTime3DsToken: Any
    orderId: Any
    payment: Any
    redirectURL: Any
    sessionId: Any
    timestamp: Any

def make_token() -> str: ...
