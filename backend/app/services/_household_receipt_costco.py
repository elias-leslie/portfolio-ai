"""Read a warehouse-club register receipt exactly, and refuse it when it does not add up.

Costco prints a receipt no general extractor reads well: the item number runs
straight into an abbreviated name with no separator, the name runs straight into
the price, a multiple-quantity line sits *above* the item it multiplies, and an
instant-savings markdown sits *below* the item it reduces. Asked to transcribe
that, a model reads a fraction of the lines and fills the rest in from whatever
else it has seen.

The format is regular, so it is parsed rather than inferred, and the receipt
proves its own reading: the items less the markdowns must equal the printed
SUBTOTAL to the cent, and the line quantities must equal the printed item count.
A receipt that fails either check is reported as unread rather than ingested at
a confidence nobody can check.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

# `E 1738408KS FR 2DZ 10.58 N` -- an optional department letter, then the item
# number welded to an abbreviated name, then the price welded to the name, then
# the taxable flag. Only the flag is reliably separated, so the line is taken
# apart from the right rather than matched in one piece.
_ITEM_TAIL = re.compile(r"^(?P<rest>.*\d)\s+(?P<flag>[A-Z])\s*$")
_DEPARTMENT_PREFIX = re.compile(r"^[A-Z]\s+")
# `2 @ 5.29` -- printed above the line it multiplies.
_QUANTITY_LINE = re.compile(r"^(?P<quantity>\d+)\s*@\s*(?P<unit_price>\d+\.\d{2})\s*$")
# `385223/ 45221 3.00-` -- coupon number, the item it reduces, the markdown.
# The reference is usually the item number and occasionally a word.
_MARKDOWN_LINE = re.compile(r"^(?P<coupon>\d+)\s*/\s*(?P<ref>\S+)\s+(?P<amount>\d+\.\d{2})-\s*$")
_LEADING_CODE = re.compile(r"^(?P<code>\d+)(?P<rest>.*)$")

_SUBTOTAL = re.compile(r"^SUBTOTAL\s+(?P<amount>\d+\.\d{2})\s*$")
_TAX = re.compile(r"^TAX\s+(?P<amount>\d+\.\d{2})\s*$")
_TOTAL = re.compile(r"^\*+\s*TOTAL\s+(?P<amount>\d+\.\d{2})\s*$")
_ITEMS_SOLD = re.compile(r"^TOTAL NUMBER OF ITEMS SOLD\s*=\s*(?P<count>\d+)\s*$")
_INSTANT_SAVINGS = re.compile(r"^INSTANT SAVINGS\s*\$?(?P<amount>\d+\.\d{2})\s*$")
_WAREHOUSE = re.compile(r"^(?P<name>[A-Z][A-Z .'-]*[A-Z])\s+#(?P<number>\d{3,4})\s*$")
# `06/23/202616:00` -- the authorisation stamp, date and 24-hour time welded.
_STAMPED_AT = re.compile(r"(?P<date>\d{2}/\d{2}/\d{4})(?P<time>\d{2}:\d{2})")
# `XXXXXXXXXXXXX9728 CHIP` -- the card, when one was used.
_CARD_LINE = re.compile(r"^X{4,}(?P<mask>\d{4})\b")
_SHOPCARD_LINE = re.compile(r"^WALLET\s*-\s*SHOPCARD\b")

# Costco item numbers run to seven digits; a longer leading run means the name
# itself starts with a digit ("11363403LB ORG GALA" is 1136340 + "3LB ORG GALA").
_MAX_ITEM_CODE_DIGITS = 7

# Lines that are furniture, not content.
_NOISE_PREFIXES = (
    "member",
    "thank you",
    "please come again",
    "whse:",
    "items sold:",
    "change ",
    "approved",
    "amount:",
    "total tax",
    "https://",
    "read",
)


@dataclass
class CostcoLineItem:
    item_code: str | None
    description: str
    quantity: int
    unit_price: Decimal
    amount: Decimal
    taxable: bool
    discount: Decimal = Decimal("0")

    @property
    def net_amount(self) -> Decimal:
        return self.amount - self.discount


@dataclass
class CostcoReceipt:
    line_items: list[CostcoLineItem]
    subtotal: Decimal | None
    tax: Decimal | None
    total: Decimal | None
    instant_savings: Decimal
    declared_items_sold: int | None
    purchased_on: date | None
    warehouse: str | None
    card_mask: str | None
    paid_with_shopcard: bool
    unreconciled: list[str] = field(default_factory=list)

    @property
    def reconciles(self) -> bool:
        return not self.unreconciled

    @property
    def item_quantity_total(self) -> int:
        return sum(item.quantity for item in self.line_items)

    @property
    def line_item_gross(self) -> Decimal:
        return sum((item.amount for item in self.line_items), Decimal("0"))

    @property
    def markdown_total(self) -> Decimal:
        return sum((item.discount for item in self.line_items), Decimal("0"))


def looks_like_costco_receipt(text: str) -> bool:
    """True when the text carries the register's own tells, not just the word Costco."""
    lowered = text.lower()
    if "costco" not in lowered and "wholesale" not in lowered:
        return False
    return "total number of items sold" in lowered or bool(_TOTAL.search(text))


def _split_trailing_price(rest: str) -> tuple[str, Decimal] | None:
    """Separate the price from the name it is printed against, with no space between.

    The name itself can end in digits ("2PK2.79") and can even contain its own
    decimal ("READERS +1.50" priced at 19.99), so the integer part is taken as
    the run of digits before the cents -- stopping at a decimal point, which
    belongs to the name and takes two of those digits with it.
    """
    if len(rest) < 4 or rest[-3] != ".":
        return None
    cents_start = len(rest) - 3
    start = cents_start
    while start > 0 and rest[start - 1].isdigit():
        start -= 1
    if start > 0 and rest[start - 1] == ".":
        # Those digits are another number's fraction; the price starts after it.
        start = min(start + 2, cents_start)
    body = rest[:start].strip()
    if not body:
        return None
    return body, Decimal(rest[start:])


def _split_item_code(body: str) -> tuple[str | None, str]:
    match = _LEADING_CODE.match(body)
    if match is None:
        return None, body.strip()
    code = match.group("code")
    rest = match.group("rest")
    if len(code) > _MAX_ITEM_CODE_DIGITS:
        rest = code[_MAX_ITEM_CODE_DIGITS:] + rest
        code = code[:_MAX_ITEM_CODE_DIGITS]
    return code, rest.strip(" *")


def _is_noise(line: str) -> bool:
    lowered = line.lower()
    return any(lowered.startswith(prefix) for prefix in _NOISE_PREFIXES)


def parse_costco_receipt(text: str) -> CostcoReceipt:
    """Read the register lines, then say plainly whether the reading holds up."""
    line_items: list[CostcoLineItem] = []
    subtotal = tax = total = None
    instant_savings = Decimal("0")
    declared_items_sold: int | None = None
    purchased_on: date | None = None
    warehouse: str | None = None
    card_mask: str | None = None
    paid_with_shopcard = False

    pending_quantity: tuple[int, Decimal] | None = None
    # A name that wrapped: the line carried no price, so its price is on the next.
    pending_name: str | None = None

    for raw_line in text.splitlines():
        line = " ".join(raw_line.split())
        if not line:
            continue

        if (matched := _SUBTOTAL.match(line)) is not None:
            subtotal = Decimal(matched.group("amount"))
            continue
        if (matched := _TAX.match(line)) is not None:
            tax = Decimal(matched.group("amount"))
            continue
        if (matched := _TOTAL.match(line)) is not None:
            total = Decimal(matched.group("amount"))
            continue
        if (matched := _ITEMS_SOLD.match(line)) is not None:
            declared_items_sold = int(matched.group("count"))
            continue
        if (matched := _INSTANT_SAVINGS.match(line)) is not None:
            instant_savings = Decimal(matched.group("amount"))
            continue
        if warehouse is None and (matched := _WAREHOUSE.match(line)) is not None:
            warehouse = f"{matched.group('name').title()} #{matched.group('number')}"
            continue
        if card_mask is None and (matched := _CARD_LINE.match(line)) is not None:
            # A register prints zeros for a card it did not read.
            mask = matched.group("mask")
            card_mask = None if mask == "0000" else mask
            continue
        if _SHOPCARD_LINE.match(line) is not None:
            paid_with_shopcard = True
            continue
        if purchased_on is None and (matched := _STAMPED_AT.search(line)) is not None:
            try:
                purchased_on = datetime.strptime(matched.group("date"), "%m/%d/%Y").date()
            except ValueError:
                purchased_on = None
            continue

        if (matched := _QUANTITY_LINE.match(line)) is not None:
            pending_quantity = (
                int(matched.group("quantity")),
                Decimal(matched.group("unit_price")),
            )
            continue

        if (matched := _MARKDOWN_LINE.match(line)) is not None:
            if line_items:
                line_items[-1].discount += Decimal(matched.group("amount"))
            continue

        if _is_noise(line):
            continue

        tail = _ITEM_TAIL.match(line)
        split = _split_trailing_price(tail.group("rest")) if tail is not None else None
        if split is None:
            # No price on this line: a name that wrapped onto the next one.
            pending_name = line
            continue

        body, amount = split
        has_department = bool(_DEPARTMENT_PREFIX.match(body))
        body = _DEPARTMENT_PREFIX.sub("", body)
        if pending_name is not None:
            # Only a continuation joins: a line that starts its own item number,
            # or carries its own department letter, is a new item and the held
            # line was register furniture (a member number, a stamp).
            if not has_department and not body[:1].isdigit():
                body = f"{_DEPARTMENT_PREFIX.sub('', pending_name)} {body}"
            pending_name = None
        item_code, description = _split_item_code(body)
        if pending_quantity is not None:
            quantity, unit_price = pending_quantity
            pending_quantity = None
        else:
            quantity, unit_price = 1, amount
        line_items.append(
            CostcoLineItem(
                item_code=item_code,
                description=" ".join(description.split()) or (item_code or "item"),
                quantity=quantity,
                unit_price=unit_price,
                amount=amount,
                taxable=tail.group("flag") == "Y",
            )
        )

    receipt = CostcoReceipt(
        line_items=line_items,
        subtotal=subtotal,
        tax=tax,
        total=total,
        instant_savings=instant_savings,
        declared_items_sold=declared_items_sold,
        purchased_on=purchased_on,
        warehouse=warehouse,
        card_mask=card_mask,
        paid_with_shopcard=paid_with_shopcard,
    )
    receipt.unreconciled = _reconcile(receipt)
    return receipt


def _reconcile(receipt: CostcoReceipt) -> list[str]:
    """Every way this reading fails to match what the register printed."""
    failures: list[str] = []
    if not receipt.line_items:
        failures.append("no line items were read")
    if receipt.subtotal is None:
        failures.append("the receipt printed no subtotal to check against")
    else:
        read_subtotal = receipt.line_item_gross - receipt.markdown_total
        if read_subtotal != receipt.subtotal:
            failures.append(
                f"items less markdowns come to {read_subtotal}, "
                f"and the receipt says {receipt.subtotal}"
            )
    if receipt.declared_items_sold is None:
        failures.append("the receipt printed no item count to check against")
    elif receipt.item_quantity_total != receipt.declared_items_sold:
        failures.append(
            f"{receipt.item_quantity_total} items were read, "
            f"and the receipt says {receipt.declared_items_sold}"
        )
    if receipt.instant_savings and receipt.markdown_total != receipt.instant_savings:
        failures.append(
            f"markdowns come to {receipt.markdown_total}, "
            f"and the receipt says {receipt.instant_savings}"
        )
    if (
        receipt.subtotal is not None
        and receipt.tax is not None
        and receipt.total is not None
        and receipt.subtotal + receipt.tax != receipt.total
    ):
        failures.append(
            f"subtotal plus tax comes to {receipt.subtotal + receipt.tax}, "
            f"and the receipt says {receipt.total}"
        )
    return failures
