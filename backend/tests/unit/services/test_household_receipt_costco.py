"""Unit tests for reading a Costco register receipt exactly."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.services._household_receipt_costco import (
    looks_like_costco_receipt,
    parse_costco_receipt,
)

# The register's own shape: an item number welded to an abbreviated name welded
# to the price, a quantity line above the item it multiplies, and an
# instant-savings markdown below the item it reduces.
_RECEIPT = """CLEARWATER #336
2655 GULF TO BAY BLVD
CLEARWATER, FL 33759
Member
111772590689
F 453914PEROXIDE 2PK2.79 N
E 96716 ORG SPINACH4.29 N
2 @ 5.29
E 1738408KS FR 2DZ 10.58 N
E 45221 CHEEZ-IT 48Z 9.99 N
385223/ 45221 3.00-
1897232ZIPLOC
SANDW 9.99 Y
385267/ 1897232 2.20-
SUBTOTAL 32.44
TAX 1.58
**** TOTAL 34.02
XXXXXXXXXXXXX9728 CHIP
08/17/202611:06336968118
TOTAL NUMBER OF ITEMS SOLD = 6
INSTANT SAVINGS $5.20
"""


def test_looks_like_costco_needs_the_registers_own_tells() -> None:
    assert looks_like_costco_receipt(_RECEIPT.replace("CLEARWATER", "COSTCO")) is True
    assert looks_like_costco_receipt("a shopping list that mentions costco") is False


def test_a_receipt_that_adds_up_says_so() -> None:
    receipt = parse_costco_receipt(_RECEIPT)
    assert receipt.reconciles, receipt.unreconciled
    assert receipt.subtotal == Decimal("32.44")
    assert receipt.total == Decimal("34.02")
    assert receipt.item_quantity_total == 6
    assert receipt.markdown_total == Decimal("5.20")


def test_the_item_number_is_split_off_the_abbreviated_name() -> None:
    items = {item.description: item for item in parse_costco_receipt(_RECEIPT).line_items}
    assert items["PEROXIDE 2PK"].item_code == "453914"
    assert items["PEROXIDE 2PK"].amount == Decimal("2.79")
    assert items["ORG SPINACH"].item_code == "96716"


def test_a_quantity_line_multiplies_the_item_printed_below_it() -> None:
    items = {item.description: item for item in parse_costco_receipt(_RECEIPT).line_items}
    fresh_eggs = items["KS FR 2DZ"]
    assert fresh_eggs.quantity == 2
    assert fresh_eggs.unit_price == Decimal("5.29")
    assert fresh_eggs.amount == Decimal("10.58")


def test_a_markdown_reduces_the_item_printed_above_it() -> None:
    items = {item.description: item for item in parse_costco_receipt(_RECEIPT).line_items}
    assert items["CHEEZ-IT 48Z"].discount == Decimal("3.00")
    assert items["CHEEZ-IT 48Z"].net_amount == Decimal("6.99")


def test_a_name_that_wrapped_onto_the_next_line_is_one_item() -> None:
    descriptions = [item.description for item in parse_costco_receipt(_RECEIPT).line_items]
    assert "ZIPLOC SANDW" in descriptions
    assert len(descriptions) == 5


def test_the_member_number_above_the_first_item_is_not_glued_to_it() -> None:
    """It carries its own department letter, so it starts an item and joins nothing."""
    first = parse_costco_receipt(_RECEIPT).line_items[0]
    assert first.item_code == "453914"
    assert "111772590689" not in first.description


def test_a_name_ending_in_digits_does_not_eat_the_price() -> None:
    receipt = parse_costco_receipt(
        "E 1738408KS FR 2DZ 10.58 N\nSUBTOTAL 10.58\nTOTAL NUMBER OF ITEMS SOLD = 1\n"
    )
    assert receipt.line_items[0].amount == Decimal("10.58")
    assert receipt.line_items[0].description == "KS FR 2DZ"


def test_a_name_carrying_its_own_decimal_keeps_it() -> None:
    """Reading glasses are '+1.50' strength and cost 19.99; neither number is the other."""
    receipt = parse_costco_receipt(
        "F 1908271READERS+1.5019.99 Y\nSUBTOTAL 19.99\nTOTAL NUMBER OF ITEMS SOLD = 1\n"
    )
    item = receipt.line_items[0]
    assert item.amount == Decimal("19.99")
    assert item.description == "READERS+1.50"


def test_a_name_starting_with_a_digit_keeps_it_out_of_the_item_number() -> None:
    receipt = parse_costco_receipt(
        "E 11363403LB ORG GALA4.69 N\nSUBTOTAL 4.69\nTOTAL NUMBER OF ITEMS SOLD = 1\n"
    )
    item = receipt.line_items[0]
    assert item.item_code == "1136340"
    assert item.description == "3LB ORG GALA"


def test_the_card_and_the_day_come_off_the_receipt() -> None:
    receipt = parse_costco_receipt(_RECEIPT)
    assert receipt.card_mask == "9728"
    assert receipt.purchased_on == date(2026, 8, 17)
    assert receipt.warehouse == "Clearwater #336"


def test_a_register_that_read_no_card_reports_none_rather_than_zeros() -> None:
    receipt = parse_costco_receipt(
        "XXXXXXXXXXXXX0000 CHIP\nWALLET - SHOPCARD 34.02\nSUBTOTAL 34.02\n"
    )
    assert receipt.card_mask is None
    assert receipt.paid_with_shopcard is True


def test_a_missed_line_is_reported_rather_than_ingested() -> None:
    """The receipt proves its own reading; a short read fails the subtotal it prints."""
    receipt = parse_costco_receipt(
        "E 96716 ORG SPINACH4.29 N\nSUBTOTAL 32.44\nTOTAL NUMBER OF ITEMS SOLD = 6\n"
    )
    assert receipt.reconciles is False
    assert any("32.44" in failure for failure in receipt.unreconciled)
    assert any("6" in failure for failure in receipt.unreconciled)


def test_a_receipt_with_nothing_to_check_against_is_not_called_read() -> None:
    receipt = parse_costco_receipt("E 96716 ORG SPINACH4.29 N\n")
    assert receipt.reconciles is False
    assert "the receipt printed no subtotal to check against" in receipt.unreconciled


def test_markdowns_that_disagree_with_the_printed_savings_are_reported() -> None:
    receipt = parse_costco_receipt(
        "E 45221 CHEEZ-IT 48Z 9.99 N\n"
        "385223/ 45221 3.00-\n"
        "SUBTOTAL 6.99\n"
        "TOTAL NUMBER OF ITEMS SOLD = 1\n"
        "INSTANT SAVINGS $5.00\n"
    )
    assert receipt.reconciles is False
    assert any("markdowns come to 3.00" in failure for failure in receipt.unreconciled)
