"""two-player + keeper roles; June-2026 catalog refresh; Amazon Prime Visa

Revision ID: cc06f6a7b8c9
Revises: d4f8a2b9c1e3
Create Date: 2026-06-10 22:30:00.000000

Re-evaluation deltas (plan section 0a, user-locked 2026-06-10):

1. ``household_credit_cards.player`` — which household member holds/applies for
   the card ("p1"/"p2"). A solo 90-day rotation exceeds Chase 5/24 within a
   year; the sustainable model is two players alternating (~2 opens/yr each).
2. ``household_credit_cards.role`` — "rotating" (participates in the 90-day
   rotation; at most one is_primary_active) or "keeper" (held permanently for a
   spend niche, e.g. Amazon Prime Visa at 5% on Amazon).
3. Seed-catalog refresh to verified June-2026 values (CSR $795 + 150k/$6k,
   Amex Platinum $895 + 175k, Amex Gold $325 + 100k, CSP 75k/$5k; cents-per-point
   to Frequent-Miler-2026: UR/MR/TYP 1.5, Capital One 1.45). Only rows still
   ``source='seed'`` are touched, so intake-refreshed rows are never clobbered.
4. New ``amazon`` reward bucket + the Amazon Prime Visa keeper-card product.
"""
import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'cc06f6a7b8c9'
down_revision: str | Sequence[str] | None = 'd4f8a2b9c1e3'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# slug -> June-2026 verified values (sources: issuer pages, TPG, Frequent Miler RRV).
_REFRESH: dict[str, dict] = {
    "chase-sapphire-preferred": {
        "annual_fee": 95, "est_point_value_cents": 1.5,
        "welcome_bonus_points": 75000, "welcome_min_spend": 5000, "welcome_window_days": 90,
    },
    "chase-sapphire-reserve": {
        "annual_fee": 795, "est_point_value_cents": 1.5,
        "welcome_bonus_points": 150000, "welcome_min_spend": 6000, "welcome_window_days": 90,
    },
    "chase-freedom-unlimited": {"est_point_value_cents": 1.5},
    "amex-gold": {
        "annual_fee": 325, "est_point_value_cents": 1.5,
        "welcome_bonus_points": 100000, "welcome_min_spend": 8000, "welcome_window_days": 180,
    },
    "amex-platinum": {
        "annual_fee": 895, "est_point_value_cents": 1.5,
        "welcome_bonus_points": 175000, "welcome_min_spend": 8000, "welcome_window_days": 180,
    },
    "capital-one-venture-x": {"est_point_value_cents": 1.45},
    "capital-one-venture": {"est_point_value_cents": 1.45},
    "citi-strata-premier": {"est_point_value_cents": 1.5},
}

# 5% Amazon/Whole Foods (with Prime), 2% dining/gas/transit, 1% elsewhere;
# points are cash-equivalent at 1.0¢. No annual fee; typical gift-card welcome.
_AMAZON_PRIME_VISA = {
    "slug": "amazon-prime-visa", "issuer": "Chase", "network": "Visa",
    "product_name": "Amazon Prime Visa", "annual_fee": 0,
    "reward_multipliers": {"amazon": 5, "dining": 2, "gas": 2, "travel": 2, "flights": 1, "groceries": 1, "other": 1},
    "point_program": "cash", "est_point_value_cents": 1.0,
    "welcome_bonus_points": 0, "welcome_bonus_cash": 150, "welcome_min_spend": 0, "welcome_window_days": 0,
    "transfer_partners": [],
    "credits": [],
    "issuer_rules": {"chase_5_24": True},
}

_INSERT = sa.text(
    """
    INSERT INTO credit_card_products (
        slug, issuer, network, product_name, card_kind, annual_fee,
        reward_multipliers, point_program, est_point_value_cents,
        welcome_bonus_points, welcome_bonus_cash, welcome_min_spend, welcome_window_days,
        transfer_partners, credits, issuer_rules, source, last_verified_at
    ) VALUES (
        :slug, :issuer, :network, :product_name, 'personal', :annual_fee,
        CAST(:reward_multipliers AS jsonb), :point_program, :est_point_value_cents,
        :welcome_bonus_points, :welcome_bonus_cash, :welcome_min_spend, :welcome_window_days,
        CAST(:transfer_partners AS jsonb), CAST(:credits AS jsonb), CAST(:issuer_rules AS jsonb),
        'seed', CURRENT_TIMESTAMP
    )
    ON CONFLICT (slug) DO NOTHING
    """
)


def upgrade() -> None:
    op.add_column(
        "household_credit_cards",
        sa.Column("player", sa.Text(), nullable=False, server_default=sa.text("'p1'")),
    )
    op.add_column(
        "household_credit_cards",
        sa.Column("role", sa.Text(), nullable=False, server_default=sa.text("'rotating'")),
    )
    op.add_column(
        "card_rotation_steps",
        sa.Column("player", sa.Text(), nullable=True),
    )

    bind = op.get_bind()
    for slug, fields in _REFRESH.items():
        sets = ", ".join(f"{col} = :{col}" for col in fields)
        bind.execute(
            sa.text(
                f"UPDATE credit_card_products SET {sets}, last_verified_at = CURRENT_TIMESTAMP "
                "WHERE slug = :slug AND source = 'seed'"
            ),
            {**fields, "slug": slug},
        )
    bind.execute(
        _INSERT,
        {
            **_AMAZON_PRIME_VISA,
            "reward_multipliers": json.dumps(_AMAZON_PRIME_VISA["reward_multipliers"]),
            "transfer_partners": json.dumps(_AMAZON_PRIME_VISA["transfer_partners"]),
            "credits": json.dumps(_AMAZON_PRIME_VISA["credits"]),
            "issuer_rules": json.dumps(_AMAZON_PRIME_VISA["issuer_rules"]),
        },
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text("DELETE FROM credit_card_products WHERE slug = 'amazon-prime-visa' AND source = 'seed'")
    )
    op.drop_column("card_rotation_steps", "player")
    op.drop_column("household_credit_cards", "role")
    op.drop_column("household_credit_cards", "player")
