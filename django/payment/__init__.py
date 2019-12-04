import aiohttp
import uuid
import decimal
import datetime
import dateutil.parser
import django_keycloak_auth.clients
from django.conf import settings


class PaymentException(Exception):
    def __init__(self, *args):
        super().__init__(*args)


class PaymentItem:
    def __init__(self, item_type: str, item_data, title: str, quantity: int, price: decimal.Decimal):
        self.__item_type = item_type
        self.__item_data = item_data
        self.__title = title
        self.__quantity = quantity
        self.__price = price

    @property
    def as_json(self):
        return {
            "item_type": self.__item_type,
            "item_data": self.__item_data,
            "title": self.__title,
            "quantity": self.__quantity,
            "price": self.__price
        }

    @property
    def item_type(self) -> str:
        return self.__item_type

    @property
    def item_data(self):
        return self.__item_data

    @property
    def price(self) -> decimal.Decimal:
        return self.__price

    @property
    def quantity(self) -> int:
        return self.__quantity

    @property
    def title(self) -> str:
        return self.__title


class Payment:
    def __init__(self, payment_id: uuid.UUID, timestamp: datetime.datetime, state: str, environment: str,
                 customer_id: uuid.UUID, items: [PaymentItem], payment_method: str):
        self.__id = payment_id
        self.__timestamp = timestamp
        self.__state = state
        self.__environment = environment
        self.__customer_id = customer_id
        self.__items = items
        self.__payment_method = payment_method

    @property
    def id(self) -> uuid.UUID:
        return self.__id

    @property
    def timestamp(self) -> datetime.datetime:
        return self.__timestamp

    @property
    def state(self) -> str:
        return self.__state

    @property
    def environment(self) -> str:
        return self.__environment

    @property
    def customer_id(self) -> uuid.UUID:
        return self.__customer_id

    @property
    def items(self) -> [PaymentItem]:
        return self.__items

    @property
    def payment_method(self) -> str:
        return self.__payment_method

    @property
    def total(self) -> decimal.Decimal:
        total = decimal.Decimal("0")
        for i in self.items:
            total += i.price * i.quantity
        return total


async def get_payment(payment_id: uuid.UUID) -> Payment:
    async with aiohttp.ClientSession() as session:
        r = await session.get(f"{settings.PAYMENT_HTTP_URL}/payment/{str(payment_id)}/")
    if r.status != 200:
        raise PaymentException()
    resp = await r.json()
    return Payment(
        payment_id=uuid.UUID(resp.get("id")),
        timestamp=dateutil.parser.isoparse(resp.get("timestamp")),
        state=resp.get("state"),
        environment=resp.get("environment"),
        customer_id=uuid.UUID(resp.get("customer", {}).get("id")),
        payment_method=resp.get("payment_method"),
        items=[PaymentItem(
            item_type=i.get("type"),
            item_data=i.get("data"),
            title=i.get("title"),
            price=decimal.Decimal(i.get("price")),
            quantity=i.get("quantity")
        ) for i in resp.get("items")]
    )


async def create_payment(environment: str, customer_id: uuid.UUID, items: [PaymentItem]) -> uuid.UUID:
    access_token = django_keycloak_auth.clients.get_new_access_token()[0].get("access_token")
    async with aiohttp.ClientSession() as session:
        r = await session.post(f"{settings.PAYMENT_HTTP_URL}/payment/new/", headers={
           "Authorization": f"Bearer {access_token}"
        }, json={
            "environment": environment,
            "customer_id": str(customer_id),
            "items": [i.as_json for i in items]
        })
    if r.status != 200:
        raise PaymentException()
    resp = await r.json()
    return uuid.UUID(resp.get("id"))
