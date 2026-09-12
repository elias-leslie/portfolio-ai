from app.services._household_merchants import _canonical_merchant_name
from app.services._household_report_builder import _merchant_aliases
from app.services._household_statement_merchants import (
    normalize_statement_merchant,
    same_statement_biller,
    statement_merchant_key,
)


def test_two_exports_of_one_electricity_bill_name_the_same_biller():
    assert normalize_statement_merchant("DIRECT DEBIT DUKEENERGY BILL PAY (Cash)") == (
        "Duke Energy"
    )
    assert normalize_statement_merchant(
        "Dukeenergy Bill Pay 910066616132 Elias B Leslie"
    ) == "Duke Energy"


def test_the_account_holders_own_name_is_not_the_merchant():
    assert normalize_statement_merchant(
        "T-Mobile PCS Svc 260114 5501668 Elias Leslie"
    ) == "T Mobile"


def test_a_truncated_spelling_still_matches_the_full_one():
    truncated = statement_merchant_key("DIRECT DEBIT FRONTIER COMMUBILL PAY (Cash)")
    full = statement_merchant_key(
        "Frontier Communi Bill Pay 260126 10252109551 Elias Leslie"
    )

    assert truncated != full
    assert same_statement_biller(truncated, full) is True


def test_two_shops_sharing_a_few_letters_are_not_one_biller():
    assert same_statement_biller("walmart", "walgreens") is False


def test_a_card_feed_merchant_is_left_alone():
    assert normalize_statement_merchant("WM SUPERCENTER #5831 | Sale") is None
    assert normalize_statement_merchant("Get Fitness") is None
    assert normalize_statement_merchant("Amazon Mktpl 1273750a3 Amzn Com Bill Wa") is None


def test_a_cheque_keeps_its_number_because_that_is_all_it_names():
    assert normalize_statement_merchant("Check Paid # 1002 (Cash)") is None


def test_a_peer_payment_keeps_the_person_it_was_paid_to():
    assert normalize_statement_merchant(
        "Venmo Payment 260117 1047668918292 Jordan Demo"
    ) is None
    assert (
        _canonical_merchant_name("Venmo Payment 260117 1047668918292 Jordan Demo")
        == "Venmo Payment 260117 1047668918292 Jordan Demo"
    )


def test_the_store_that_rang_up_a_card_charge_is_not_a_separate_merchant():
    assert _canonical_merchant_name("PUBLIX #1309 | Sale") == "Publix"
    assert _canonical_merchant_name("Publix") == "Publix"
    assert _canonical_merchant_name("SPEEDWAY 43370 | Sale") == "Speedway"


def test_walmarts_store_number_is_kept_because_the_household_shops_at_one():
    assert _canonical_merchant_name("WM SUPERCENTER #5831 | Sale") == (
        "Walmart (Store #5831)"
    )


def test_a_long_all_caps_description_is_not_title_cased_into_nonsense():
    assert "12Th" not in _canonical_merchant_name(
        "ZELLE FROM MICHAEL WILEY ON 12/31 REF # BACPC0VVAKEH 12TH MORTGAGE PAY"
    )


def test_bank_transport_prefix_cannot_merge_unrelated_merchants():
    grocery = "DEBIT CARD PURCHASE PUBLIX SUPER MARKETS ANYTOWN FL090326 AUTHID:040132 (Cash)"
    peer = "DEBIT CARD PURCHASE CASH APP JORDAN DEMO OAKLAND CA090326 AUTHID:652863 (Cash)"
    assert _canonical_merchant_name(grocery) == "Publix"
    assert not same_statement_biller(statement_merchant_key(grocery), statement_merchant_key(peer))
    assert not (_merchant_aliases(grocery) & _merchant_aliases(peer))


def test_bank_peer_payments_preserve_distinct_recipients():
    left = "DEBIT CARD PURCHASE CASH APP JORDAN DEMO 123456 (Cash)"
    right = "DEBIT CARD PURCHASE CASH APP TAYLOR DEMO 123456 (Cash)"
    assert _canonical_merchant_name(left) != _canonical_merchant_name(right)
    assert not (_merchant_aliases(left) & _merchant_aliases(right))


def test_shared_nine_characters_are_not_evidence_of_one_business():
    assert not same_statement_biller("debitcardpurchasepublix", "debitcardpurchasecashapp")
    assert not same_statement_biller("nationalbank", "nationalbakery")


def test_publix_statement_variants_match_card_feed_identity():
    assert _canonical_merchant_name("DEBIT CARD PURCHASE PUBLIX #1309 FL090326 (Cash)") == "Publix"
    assert _merchant_aliases("DEBIT CARD PURCHASE PUBLIX #1309 FL090326 (Cash)") & _merchant_aliases("Publix")
