"""Unit tests for reading a Walmart order page exactly."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.services._household_receipt_walmart import (
    looks_like_walmart_order_page,
    looks_like_walmart_store_receipt,
    parse_walmart_order_page,
    parse_walmart_store_receipt,
)

# The page's own shape: the fulfilment note sits between the product name and
# the quantity, and carries a number that is not the quantity.
_ORDER = """Invoice
Aug 10, 2026 order
Order# 2000152-55923443
Fresh Hass Avocados, Each 30 shopped Qty 10 $8.20
Mae Ploy Sweet Chili Sauce, 12 Oz 1 substituted Qty 1 $3.22
Fresh Banana, Each 18 weight adjusted Qty 8 $1.49
Fresh Zucchini, Each Unavailable Qty 2 $1.52
Fresh Mini Cucumbers, 16 oz Return to Walmart store Qty 3 $6.24
Subtotal $19.15
Savings -$5.90
$13.25
Tax $0.00
Total $13.25
Order# 2000152-55923443
https://www.walmart.com/orders/200015255923443
"""


def test_looks_like_a_walmart_order_page() -> None:
    assert looks_like_walmart_order_page(_ORDER) is True
    assert looks_like_walmart_order_page("a note that mentions walmart") is False


def test_a_page_that_adds_up_says_so() -> None:
    order = parse_walmart_order_page(_ORDER)
    assert order.reconciles, order.unreconciled
    assert order.ordered_on == date(2026, 8, 10)
    assert order.order_number == "2000152-55923443"


def test_the_quantity_is_the_one_after_qty_not_the_one_in_the_fulfilment_note() -> None:
    items = {item.description: item for item in parse_walmart_order_page(_ORDER).line_items}
    avocados = items["Fresh Hass Avocados, Each"]
    assert avocados.quantity == 10
    assert avocados.amount == Decimal("8.20")
    assert avocados.fulfilment == "shopped"


def test_a_weight_adjusted_line_reads_like_any_other() -> None:
    items = {item.description: item for item in parse_walmart_order_page(_ORDER).line_items}
    bananas = items["Fresh Banana, Each"]
    assert bananas.quantity == 8
    assert bananas.amount == Decimal("1.49")
    assert bananas.fulfilment == "weight adjusted"


def test_an_item_the_store_could_not_supply_is_not_billed() -> None:
    """It is what the household asked for, not what it paid for, and the subtotal agrees."""
    order = parse_walmart_order_page(_ORDER)
    unavailable = next(item for item in order.line_items if item.fulfilment == "unavailable")
    assert unavailable.billed is False
    assert order.line_item_total == Decimal("19.15")
    assert order.reconciles


def test_a_returned_item_was_still_charged_and_still_counts_toward_the_subtotal() -> None:
    order = parse_walmart_order_page(_ORDER)
    returned = next(item for item in order.line_items if item.returned)
    assert returned.billed is True
    assert returned.quantity == 3
    assert order.item_quantity_total == 19


def test_the_charge_is_the_total_and_not_the_subtotal() -> None:
    """The subtotal is the order before its savings, and is never what the card sees."""
    order = parse_walmart_order_page(_ORDER)
    assert order.subtotal == Decimal("19.15")
    assert order.savings == Decimal("5.90")
    assert order.total == Decimal("13.25")


def test_a_page_whose_items_miss_the_subtotal_is_reported_rather_than_ingested() -> None:
    order = parse_walmart_order_page(
        "Order# 1\nFresh Banana, Each 18 weight adjusted Qty 8 $1.49\n"
        "Subtotal $19.15\nTax $0.00\nTotal $19.15\n"
    )
    assert order.reconciles is False
    assert any("19.15" in failure for failure in order.unreconciled)


def test_a_page_that_saved_with_no_content_is_named_as_empty() -> None:
    order = parse_walmart_order_page("Return to previous page\nOrder details - Walmart.com\n")
    assert order.reconciles is False
    assert "no line items were read" in order.unreconciled


def test_savings_that_do_not_bridge_subtotal_and_total_are_reported() -> None:
    order = parse_walmart_order_page(
        "Order# 1\nFresh Banana, Each 18 weight adjusted Qty 8 $1.49\n"
        "Subtotal $1.49\nSavings -$0.50\nTax $0.00\nTotal $1.49\n"
    )
    assert order.reconciles is False
    assert any("subtotal less savings" in failure for failure in order.unreconciled)


# The register tape as it survives extraction: one value per line, and one
# block that lost its price on the way through.
_STORE_TAPE = """Return to previous page
8/22/26, 8:38 AM Order details - Walmart.com
https://www.walmart.com/orders/73343837301188501734?groupId=0&storePurchase=true 1/1
Walmart
Save money. Live better.
WAL*MART
7275550100Mgr.SAMPLE
LARGO, FL
ST#1000OP#9011TE#11TR#565
CWY 36CT CH
003000056623F
8.77
CI ORIG FAM
002410044070F
5.37
RITZ
004400088210F
3.96
004400088211F
SUBTOTAL
22.06
TAX 12
0%
0.00
TOTAL
VISA
CREDIT
TEND
****
1234
CHANGE DUE
"""

_WHOLE_TAPE = """WAL*MART
ST#1000OP#9011TE#11TR#565
CWY 36CT CH
003000056623F
8.77
CI ORIG FAM
002410044070F
5.37
SUBTOTAL
14.14
TAX 12
7%
0.99
TOTAL
15.13
VISA
****
1234
"""


def test_a_store_tape_is_not_read_as_an_order_page() -> None:
    assert looks_like_walmart_store_receipt(_STORE_TAPE) is True
    assert looks_like_walmart_order_page(_STORE_TAPE) is False


def test_the_charge_is_read_even_when_a_line_lost_its_price() -> None:
    receipt = parse_walmart_store_receipt(_STORE_TAPE)

    # The tape states what the card paid, and says so plainly enough to trust.
    assert receipt.subtotal == Decimal("22.06")
    assert receipt.tax == Decimal("0.00")
    assert receipt.charged == Decimal("22.06")
    assert receipt.charge_reconciles is True


def test_an_unreadable_line_is_reported_rather_than_guessed() -> None:
    receipt = parse_walmart_store_receipt(_STORE_TAPE)

    assert receipt.items_reconcile is False
    assert len(receipt.line_items) == 4
    unreadable = [item for item in receipt.line_items if not item.readable]
    assert [item.upc for item in unreadable] == ["004400088211"]
    # The gap is named with both halves of the arithmetic, so a person can see
    # exactly how much of the receipt was not read.
    assert any("18.10" in failure and "22.06" in failure for failure in receipt.itemisation_failures)


def test_the_tape_names_the_card_that_paid() -> None:
    receipt = parse_walmart_store_receipt(_STORE_TAPE)

    assert receipt.card_mask == "1234"
    assert receipt.card_label == "VISA"
    assert receipt.store_number == "1000"


def test_a_tape_that_reads_whole_reconciles_on_both_counts() -> None:
    receipt = parse_walmart_store_receipt(_WHOLE_TAPE)

    assert receipt.charge_reconciles is True
    assert receipt.items_reconcile is True
    assert receipt.printed_total == Decimal("15.13")
    assert receipt.charged == Decimal("15.13")
    assert [item.description for item in receipt.line_items] == ["CWY 36CT CH", "CI ORIG FAM"]


def test_a_missing_total_is_not_taken_from_the_tender_below_it() -> None:
    receipt = parse_walmart_store_receipt(_STORE_TAPE)

    # `TOTAL` is followed by the card, not by an amount. Reading the next number
    # on the tape would have taken a tender or change figure for the total.
    assert receipt.printed_total is None
