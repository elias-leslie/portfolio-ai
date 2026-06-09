"""seed representative credit_card_products catalog

Revision ID: cc05e5f6a7b8
Revises: cc04d4e5f6a7
Create Date: 2026-06-09 09:04:00.000000

Seeds a representative set of personal cards (plan section 2). Values model
publicly known reward structures as of mid-2026 and are marked verify-at-apply
via last_verified_at; offer intake extends/refreshes the catalog. Idempotent via
ON CONFLICT (slug) DO NOTHING so seeds are never clobbered.

Reward multipliers are keyed by canonical reward bucket: dining, travel, flights,
groceries, gas, other. Point valuations are the balanced/TPG-style floor (cents
per point), never the optimistic transfer ceiling.
"""
import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'cc05e5f6a7b8'
down_revision: str | Sequence[str] | None = 'cc04d4e5f6a7'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# slug, issuer, network, product_name, annual_fee, multipliers, point_program,
# cpp, welcome_points, welcome_cash, welcome_min_spend, welcome_window_days,
# transfer_partners, credits, issuer_rules
_SEED: list[dict] = [
    {
        "slug": "chase-sapphire-preferred", "issuer": "Chase", "network": "Visa",
        "product_name": "Chase Sapphire Preferred", "annual_fee": 95,
        "reward_multipliers": {"dining": 3, "travel": 2, "flights": 5, "groceries": 3, "gas": 1, "other": 1},
        "point_program": "ultimate_rewards", "est_point_value_cents": 1.8,
        "welcome_bonus_points": 60000, "welcome_bonus_cash": 0, "welcome_min_spend": 4000, "welcome_window_days": 90,
        "transfer_partners": ["United", "Hyatt", "Southwest", "British Airways", "Air Canada", "Marriott"],
        "credits": [{"name": "Hotel credit", "annual_value": 50, "type": "moderate"}],
        "issuer_rules": {"chase_5_24": True, "bonus_once_per_months": 48, "family": "sapphire"},
    },
    {
        "slug": "chase-sapphire-reserve", "issuer": "Chase", "network": "Visa",
        "product_name": "Chase Sapphire Reserve", "annual_fee": 795,
        "reward_multipliers": {"dining": 3, "travel": 4, "flights": 4, "groceries": 1, "gas": 1, "other": 1},
        "point_program": "ultimate_rewards", "est_point_value_cents": 1.8,
        "welcome_bonus_points": 75000, "welcome_bonus_cash": 0, "welcome_min_spend": 5000, "welcome_window_days": 90,
        "transfer_partners": ["United", "Hyatt", "Southwest", "British Airways", "Air Canada", "Marriott"],
        "credits": [
            {"name": "Annual travel credit", "annual_value": 300, "type": "easy"},
            {"name": "Dining & entertainment credits", "annual_value": 300, "type": "hard"},
        ],
        "issuer_rules": {"chase_5_24": True, "bonus_once_per_months": 48, "family": "sapphire"},
    },
    {
        "slug": "capital-one-venture-x", "issuer": "Capital One", "network": "Visa",
        "product_name": "Capital One Venture X", "annual_fee": 395,
        "reward_multipliers": {"dining": 2, "travel": 2, "flights": 5, "groceries": 2, "gas": 2, "other": 2},
        "point_program": "capital_one_miles", "est_point_value_cents": 1.85,
        "welcome_bonus_points": 75000, "welcome_bonus_cash": 0, "welcome_min_spend": 4000, "welcome_window_days": 90,
        "transfer_partners": ["Air Canada", "Turkish", "British Airways", "Air France/KLM", "Wyndham"],
        "credits": [
            {"name": "Travel credit (portal)", "annual_value": 300, "type": "moderate"},
            {"name": "Anniversary miles (10k)", "annual_value": 185, "type": "easy"},
        ],
        "issuer_rules": {"capital_one_1_per_6mo": True, "pulls_all_bureaus": True},
    },
    {
        "slug": "capital-one-venture", "issuer": "Capital One", "network": "Visa",
        "product_name": "Capital One Venture", "annual_fee": 95,
        "reward_multipliers": {"dining": 2, "travel": 2, "flights": 5, "groceries": 2, "gas": 2, "other": 2},
        "point_program": "capital_one_miles", "est_point_value_cents": 1.85,
        "welcome_bonus_points": 75000, "welcome_bonus_cash": 0, "welcome_min_spend": 4000, "welcome_window_days": 90,
        "transfer_partners": ["Air Canada", "Turkish", "British Airways", "Air France/KLM", "Wyndham"],
        "credits": [],
        "issuer_rules": {"capital_one_1_per_6mo": True, "pulls_all_bureaus": True},
    },
    {
        "slug": "amex-gold", "issuer": "American Express", "network": "Amex",
        "product_name": "American Express Gold Card", "annual_fee": 325,
        "reward_multipliers": {"dining": 4, "travel": 1, "flights": 3, "groceries": 4, "gas": 1, "other": 1},
        "point_program": "membership_rewards", "est_point_value_cents": 2.0,
        "welcome_bonus_points": 60000, "welcome_bonus_cash": 0, "welcome_min_spend": 6000, "welcome_window_days": 180,
        "transfer_partners": ["Delta", "ANA", "Air Canada", "British Airways", "Hilton", "Marriott"],
        "credits": [
            {"name": "Dining credit", "annual_value": 120, "type": "hard"},
            {"name": "Uber Cash", "annual_value": 120, "type": "hard"},
            {"name": "Resy credit", "annual_value": 100, "type": "hard"},
        ],
        "issuer_rules": {"amex_once_per_lifetime": True, "holding_limit_credit": 5},
    },
    {
        "slug": "amex-platinum", "issuer": "American Express", "network": "Amex",
        "product_name": "The Platinum Card from American Express", "annual_fee": 695,
        "reward_multipliers": {"dining": 1, "travel": 5, "flights": 5, "groceries": 1, "gas": 1, "other": 1},
        "point_program": "membership_rewards", "est_point_value_cents": 2.0,
        "welcome_bonus_points": 80000, "welcome_bonus_cash": 0, "welcome_min_spend": 8000, "welcome_window_days": 180,
        "transfer_partners": ["Delta", "ANA", "Air Canada", "British Airways", "Hilton", "Marriott"],
        "credits": [
            {"name": "Airline incidental credit", "annual_value": 200, "type": "hard"},
            {"name": "Hotel credit (FHR/THC)", "annual_value": 200, "type": "moderate"},
            {"name": "Uber Cash", "annual_value": 200, "type": "hard"},
            {"name": "CLEAR Plus credit", "annual_value": 189, "type": "moderate"},
            {"name": "Digital entertainment credit", "annual_value": 240, "type": "hard"},
        ],
        "issuer_rules": {"amex_once_per_lifetime": True, "holding_limit_credit": 5},
    },
    {
        "slug": "citi-strata-premier", "issuer": "Citi", "network": "Mastercard",
        "product_name": "Citi Strata Premier", "annual_fee": 95,
        "reward_multipliers": {"dining": 3, "travel": 3, "flights": 3, "groceries": 3, "gas": 3, "other": 1},
        "point_program": "citi_thankyou", "est_point_value_cents": 1.8,
        "welcome_bonus_points": 70000, "welcome_bonus_cash": 0, "welcome_min_spend": 4000, "welcome_window_days": 90,
        "transfer_partners": ["Turkish", "Air France/KLM", "JetBlue", "Choice", "Wyndham"],
        "credits": [{"name": "Annual hotel credit ($500 stay)", "annual_value": 100, "type": "hard"}],
        "issuer_rules": {"bonus_once_per_months": 48},
    },
    {
        "slug": "wells-fargo-autograph", "issuer": "Wells Fargo", "network": "Visa",
        "product_name": "Wells Fargo Autograph", "annual_fee": 0,
        "reward_multipliers": {"dining": 3, "travel": 3, "flights": 3, "groceries": 1, "gas": 3, "other": 1},
        "point_program": "wells_fargo_rewards", "est_point_value_cents": 1.0,
        "welcome_bonus_points": 20000, "welcome_bonus_cash": 0, "welcome_min_spend": 1000, "welcome_window_days": 90,
        "transfer_partners": [],
        "credits": [],
        "issuer_rules": {},
    },
    {
        "slug": "chase-freedom-unlimited", "issuer": "Chase", "network": "Visa",
        "product_name": "Chase Freedom Unlimited", "annual_fee": 0,
        "reward_multipliers": {"dining": 3, "travel": 5, "flights": 5, "groceries": 1, "gas": 1, "other": 1.5},
        "point_program": "ultimate_rewards", "est_point_value_cents": 1.8,
        "welcome_bonus_points": 0, "welcome_bonus_cash": 200, "welcome_min_spend": 500, "welcome_window_days": 90,
        "transfer_partners": ["United", "Hyatt", "Southwest", "British Airways", "Air Canada", "Marriott"],
        "credits": [],
        "issuer_rules": {"chase_5_24": True},
    },
]

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
    """Insert the representative seed catalog (idempotent)."""
    bind = op.get_bind()
    for row in _SEED:
        bind.execute(
            _INSERT,
            {
                **row,
                "reward_multipliers": json.dumps(row["reward_multipliers"]),
                "transfer_partners": json.dumps(row["transfer_partners"]),
                "credits": json.dumps(row["credits"]),
                "issuer_rules": json.dumps(row["issuer_rules"]),
            },
        )


def downgrade() -> None:
    """Remove only the seed rows (leaves intake-added rows intact)."""
    bind = op.get_bind()
    slugs = tuple(row["slug"] for row in _SEED)
    bind.execute(
        sa.text("DELETE FROM credit_card_products WHERE source = 'seed' AND slug IN :slugs").bindparams(
            sa.bindparam("slugs", value=slugs, expanding=True)
        )
    )
