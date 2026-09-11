"""Read a Walmart order page exactly, and refuse it when it does not add up.

The order page prints one line per item with no separators: the product name, a
fulfilment note, the quantity and the price all run together. The fulfilment
note carries a number of its own -- ``Fresh Hass Avocados, Each 30 shopped Qty
10 $8.20`` is ten avocados, not thirty -- so a reader that takes the first
number it sees gets the count wrong on every line, and one that takes the first
total gets the *subtotal*, which is what the order cost before its savings and
is never what the card was charged.

So the line is taken apart from the right, where it is unambiguous, and the page
proves its own reading: the items must equal the printed subtotal to the cent,
and subtotal less savings plus tax must equal the printed total.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

# `Marketside Fresh Baby Spinach, 11 oz 26 shopped Qty 1 $3.77`
_ITEM_LINE = re.compile(
    r"^(?P<body>.+?)\s+Qty\s+(?P<quantity>\d+)\s+\$(?P<amount>\d[\d,]*\.\d{2})\s*$"
)
# What the store did with the line, printed between the name and the quantity.
# The leading number belongs to the note, not to the order.
_FULFILMENT = re.compile(
    r"\s+(?:(?P<count>\d+)\s+)?(?P<state>shopped|substituted|weight adjusted)$",
    flags=re.IGNORECASE,
)
_UNAVAILABLE = re.compile(r"\s+Unavailable$", flags=re.IGNORECASE)
_RETURNED = re.compile(r"\s+Return(?:ed)? to Walmart store$", flags=re.IGNORECASE)

_SUBTOTAL = re.compile(r"^Subtotal\s+\$(?P<amount>\d[\d,]*\.\d{2})\s*$", flags=re.IGNORECASE)
_SAVINGS = re.compile(r"^Savings\s+-?\$(?P<amount>\d[\d,]*\.\d{2})\s*$", flags=re.IGNORECASE)
_TAX = re.compile(r"^Tax\s+\$(?P<amount>\d[\d,]*\.\d{2})\s*$", flags=re.IGNORECASE)
_TOTAL = re.compile(r"^Total\s+\$(?P<amount>\d[\d,]*\.\d{2})\s*$", flags=re.IGNORECASE)
_ORDER_NUMBER = re.compile(r"^Order#\s*(?P<number>[\w-]+)\s*$", flags=re.IGNORECASE)
_ORDER_DATE = re.compile(r"^(?P<date>[A-Z][a-z]{2}\s+\d{1,2},\s+\d{4})\s+order\s*$")


@dataclass
class WalmartLineItem:
    description: str
    quantity: int
    amount: Decimal
    fulfilment: str
    # A line the store took back. It still sits in the printed subtotal, so it
    # has to be read, but it is not something the household now owns.
    returned: bool = False

    @property
    def billed(self) -> bool:
        """Whether this line reached the subtotal.

        An item the store could not supply is printed with its price and left
        out of the total -- it is what the household asked for, not what it paid
        for. A returned item is the other way round: it was supplied, billed,
        and refunded separately, so it stays in.
        """
        return self.fulfilment != "unavailable"


@dataclass
class WalmartOrder:
    line_items: list[WalmartLineItem]
    subtotal: Decimal | None
    savings: Decimal
    tax: Decimal | None
    total: Decimal | None
    ordered_on: date | None
    order_number: str | None
    unreconciled: list[str] = field(default_factory=list)

    @property
    def reconciles(self) -> bool:
        return not self.unreconciled

    @property
    def line_item_total(self) -> Decimal:
        return sum((item.amount for item in self.line_items if item.billed), Decimal("0"))

    @property
    def item_quantity_total(self) -> int:
        return sum(
            item.quantity
            for item in self.line_items
            if item.billed and not item.returned
        )


def looks_like_walmart_order_page(text: str) -> bool:
    lowered = text.lower()
    if "walmart" not in lowered:
        return False
    return "order#" in lowered and bool(_SUBTOTAL.search(text) or "qty" in lowered)


def _money(value: str) -> Decimal:
    return Decimal(value.replace(",", ""))


def _split_fulfilment(body: str) -> tuple[str, str, bool]:
    """Separate the store's note from the product name it follows."""
    if (matched := _RETURNED.search(body)) is not None:
        return body[: matched.start()].strip(), "returned", True
    if (matched := _UNAVAILABLE.search(body)) is not None:
        return body[: matched.start()].strip(), "unavailable", False
    if (matched := _FULFILMENT.search(body)) is not None:
        return body[: matched.start()].strip(), matched.group("state").lower(), False
    return body.strip(), "unstated", False


def parse_walmart_order_page(text: str) -> WalmartOrder:
    line_items: list[WalmartLineItem] = []
    subtotal = tax = total = None
    savings = Decimal("0")
    ordered_on: date | None = None
    order_number: str | None = None

    for raw_line in text.splitlines():
        line = " ".join(raw_line.split())
        if not line:
            continue
        if (matched := _SUBTOTAL.match(line)) is not None:
            subtotal = _money(matched.group("amount"))
            continue
        if (matched := _SAVINGS.match(line)) is not None:
            savings = _money(matched.group("amount"))
            continue
        if (matched := _TAX.match(line)) is not None:
            tax = _money(matched.group("amount"))
            continue
        if (matched := _TOTAL.match(line)) is not None:
            total = _money(matched.group("amount"))
            continue
        if order_number is None and (matched := _ORDER_NUMBER.match(line)) is not None:
            order_number = matched.group("number")
            continue
        if ordered_on is None and (matched := _ORDER_DATE.match(line)) is not None:
            try:
                ordered_on = datetime.strptime(matched.group("date"), "%b %d, %Y").date()
            except ValueError:
                ordered_on = None
            continue
        if (matched := _ITEM_LINE.match(line)) is None:
            continue
        description, fulfilment, returned = _split_fulfilment(matched.group("body"))
        if not description:
            continue
        line_items.append(
            WalmartLineItem(
                description=description,
                quantity=int(matched.group("quantity")),
                amount=_money(matched.group("amount")),
                fulfilment=fulfilment,
                returned=returned,
            )
        )

    order = WalmartOrder(
        line_items=line_items,
        subtotal=subtotal,
        savings=savings,
        tax=tax,
        total=total,
        ordered_on=ordered_on,
        order_number=order_number,
    )
    order.unreconciled = _reconcile(order)
    return order


def _reconcile(order: WalmartOrder) -> list[str]:
    failures: list[str] = []
    if not order.line_items:
        failures.append("no line items were read")
    if order.subtotal is None:
        failures.append("the page printed no subtotal to check against")
    elif order.line_item_total != order.subtotal:
        failures.append(
            f"the items come to {order.line_item_total}, "
            f"and the page says {order.subtotal}"
        )
    if order.total is None:
        failures.append("the page printed no total to check against")
    elif order.subtotal is not None:
        charged = order.subtotal - order.savings + (order.tax or Decimal("0"))
        if charged != order.total:
            failures.append(
                f"subtotal less savings plus tax comes to {charged}, "
                f"and the page says {order.total}"
            )
    return failures


# ---------------------------------------------------------------------------
# The in-store register receipt
#
# A store purchase reaches the same Walmart order URL, but what it prints is the
# register tape, not the order page, and the extraction comes out one value per
# line: the product name, then its UPC with a tax flag, then its price. Some
# blocks lose the price line entirely, which is the whole reason the charge and
# the itemisation are judged apart below -- the tape states what the card paid
# even on a receipt whose items cannot all be read.
# ---------------------------------------------------------------------------

# `003000056623F` -- the UPC and its tax flag, which is what closes an item.
_STORE_UPC = re.compile(r"^(?P<upc>\d{9,14})\s*(?P<tax_flag>[A-Z])$")
_STORE_MONEY = re.compile(r"^(?P<amount>\d[\d,]*\.\d{2})$")
_STORE_MASK = re.compile(r"^(?P<mask>\d{4})$")
_STORE_NUMBER = re.compile(r"ST#\s*(?P<store>\d+)")
_CARD_BRANDS = ("VISA", "MASTERCARD", "AMEX", "DISCOVER", "DEBIT")


@dataclass
class WalmartStoreLine:
    upc: str
    tax_flag: str
    description: str | None
    amount: Decimal | None

    @property
    def readable(self) -> bool:
        return self.description is not None and self.amount is not None


@dataclass
class WalmartStoreReceipt:
    line_items: list[WalmartStoreLine]
    subtotal: Decimal | None
    tax: Decimal | None
    printed_total: Decimal | None
    card_label: str | None
    card_mask: str | None
    store_number: str | None
    # Kept apart on purpose: a receipt can state its charge plainly while one of
    # its item prices never made it through extraction.
    itemisation_failures: list[str] = field(default_factory=list)
    charge_failures: list[str] = field(default_factory=list)

    @property
    def charged(self) -> Decimal | None:
        """What the card paid: the printed total, or subtotal plus tax."""
        if self.printed_total is not None:
            return self.printed_total
        if self.subtotal is None:
            return None
        return self.subtotal + (self.tax or Decimal("0"))

    @property
    def charge_reconciles(self) -> bool:
        return self.charged is not None and not self.charge_failures

    @property
    def items_reconcile(self) -> bool:
        return not self.itemisation_failures

    @property
    def line_item_total(self) -> Decimal:
        return sum(
            (item.amount for item in self.line_items if item.amount is not None),
            Decimal("0"),
        )


def looks_like_walmart_store_receipt(text: str) -> bool:
    upper = text.upper()
    if "WAL*MART" not in upper and "WALMART" not in upper:
        return False
    # The register tape names its lane; the order page never does.
    return "ST#" in upper and "SUBTOTAL" in upper


def _next_money(lines: list[str], start: int, *, within: int) -> tuple[Decimal | None, int]:
    """The next printed amount, when it comes soon enough to belong to the label."""
    for offset in range(start, min(start + within, len(lines))):
        if (matched := _STORE_MONEY.match(lines[offset])) is not None:
            return _money(matched.group("amount")), offset
    return None, start


def parse_walmart_store_receipt(text: str) -> WalmartStoreReceipt:
    lines = [" ".join(raw.split()) for raw in text.splitlines()]
    lines = [line for line in lines if line]

    line_items: list[WalmartStoreLine] = []
    subtotal = tax = printed_total = None
    card_label = card_mask = store_number = None
    consumed: set[int] = set()

    for index, line in enumerate(lines):
        if store_number is None and (matched := _STORE_NUMBER.search(line)) is not None:
            store_number = matched.group("store")
        if line.upper().startswith("SUBTOTAL"):
            subtotal, position = _next_money(lines, index + 1, within=2)
            consumed.add(position)
            continue
        if line.upper().startswith("TAX"):
            # `TAX 12` names the tax code and `0%` the rate; the money follows.
            tax, position = _next_money(lines, index + 1, within=3)
            consumed.add(position)
            continue
        if line.upper().startswith("TOTAL"):
            # Only when it is printed on the very next line: on a tape whose
            # total was lost, the next amount belongs to the tender below it.
            if index + 1 < len(lines) and (
                matched := _STORE_MONEY.match(lines[index + 1])
            ) is not None:
                printed_total = _money(matched.group("amount"))
                consumed.add(index + 1)
            continue
        if card_label is None and any(brand in line.upper() for brand in _CARD_BRANDS):
            card_label = line.strip()
            continue
        if line.startswith("****"):
            digits = line.lstrip("*").strip()
            if (matched := _STORE_MASK.match(digits)) is not None:
                card_mask = matched.group("mask")
            elif index + 1 < len(lines) and (
                matched := _STORE_MASK.match(lines[index + 1])
            ) is not None:
                card_mask = matched.group("mask")
                consumed.add(index + 1)
            continue

    for index, line in enumerate(lines):
        matched = _STORE_UPC.match(line)
        if matched is None:
            continue
        amount = None
        if (
            index + 1 < len(lines)
            and index + 1 not in consumed
            and (money := _STORE_MONEY.match(lines[index + 1])) is not None
        ):
            amount = _money(money.group("amount"))
            consumed.add(index + 1)
        description = None
        if index - 1 >= 0 and index - 1 not in consumed:
            candidate = lines[index - 1]
            if (
                _STORE_UPC.match(candidate) is None
                and _STORE_MONEY.match(candidate) is None
            ):
                description = candidate
                consumed.add(index - 1)
        line_items.append(
            WalmartStoreLine(
                upc=matched.group("upc"),
                tax_flag=matched.group("tax_flag"),
                description=description,
                amount=amount,
            )
        )

    receipt = WalmartStoreReceipt(
        line_items=line_items,
        subtotal=subtotal,
        tax=tax,
        printed_total=printed_total,
        card_label=card_label,
        card_mask=card_mask,
        store_number=store_number,
    )
    receipt.charge_failures = _reconcile_store_charge(receipt)
    receipt.itemisation_failures = _reconcile_store_items(receipt)
    return receipt


def _reconcile_store_charge(receipt: WalmartStoreReceipt) -> list[str]:
    failures: list[str] = []
    if receipt.subtotal is None:
        failures.append("the tape printed no subtotal")
        return failures
    if receipt.printed_total is not None:
        charged = receipt.subtotal + (receipt.tax or Decimal("0"))
        if charged != receipt.printed_total:
            failures.append(
                f"subtotal plus tax comes to {charged}, "
                f"and the tape says {receipt.printed_total}"
            )
    return failures


def _reconcile_store_items(receipt: WalmartStoreReceipt) -> list[str]:
    failures: list[str] = []
    if not receipt.line_items:
        failures.append("no line items were read")
        return failures
    unreadable = [item for item in receipt.line_items if not item.readable]
    if unreadable:
        missing_price = sum(1 for item in unreadable if item.amount is None)
        failures.append(
            f"{len(unreadable)} of {len(receipt.line_items)} lines came through "
            f"incomplete ({missing_price} with no price)"
        )
    if receipt.subtotal is not None and receipt.line_item_total != receipt.subtotal:
        failures.append(
            f"the items come to {receipt.line_item_total}, "
            f"and the tape says {receipt.subtotal}"
        )
    return failures
