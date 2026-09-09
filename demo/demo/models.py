import dataclasses
import decimal
import enum


class Sort(enum.StrEnum):
    NEWEST = "newest"
    PRICE = "price"


@dataclasses.dataclass(frozen=True, slots=True)
class Customer:
    id: int
    name: str
    email: str


class OrderBook:
    """Stands in for a repository that has to be closed when the request ends."""

    def __init__(self) -> None:
        self.orders = {42: [decimal.Decimal("649.00"), decimal.Decimal("779.00")]}

    def lifetime_value(self, customer_id: int) -> decimal.Decimal:
        return sum(self.orders.get(customer_id, []), decimal.Decimal("0.00"))


class Catalog:
    """Loaded once at startup and shared by every request."""

    def __init__(self) -> None:
        self.products = {"DSK-01": "Standing desk", "CHR-07": "Ergonomic chair"}
