import typing

from demo.models import Catalog, Customer, OrderBook
from kupala.dependencies import Factory, FromState, Value


def load_customer() -> Customer:
    """A plain factory: in a real app this would read the session."""

    return Customer(id=42, name="Marta Kowalska", email="marta@northwind.pl")


def open_order_book() -> typing.Iterator[OrderBook]:
    """A generator factory: whatever follows the yield runs after the response is sent."""

    book = OrderBook()
    try:
        yield book
    finally:
        print("ORDER BOOK CLOSED")


type CurrentCustomer = typing.Annotated[Customer, Factory(load_customer)]
type Orders = typing.Annotated[OrderBook, Factory(open_order_book)]
type Currency = typing.Annotated[str, Value("EUR")]
# whatever the lifespan yields lands on the state of every request
type ProductCatalog = typing.Annotated[Catalog, FromState(lambda ctx, state: state.catalog)]
