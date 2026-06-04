"""SnapTrade read-only brokerage data integration."""

from __future__ import annotations

import json
import re
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, cast

from snaptrade_client import SnapTrade
from snaptrade_client.exceptions import ApiException

from app.logging_config import get_logger
from app.portfolio.account_valuation import mark_to_market_account_value
from app.portfolio.models import PriceData
from app.portfolio.price_fetcher import PriceDataFetcher
from app.portfolio.watchlist_sync import ensure_symbols_in_watchlist
from app.services.credential_crypto import (
    CredentialCipher,
    SecretDecryptionError,
    SecretKeyUnavailableError,
)
from app.services.household_account_identity import account_masks_match
from app.services.source_credentials import get_source_credentials, set_source_credential
from app.storage import PortfolioStorage, get_storage

logger = get_logger(__name__)

_SNAPTRADE_SOURCE_ID = "snaptrade"
_DEFAULT_BROKER = "FIDELITY"
_READ_ONLY_CONNECTION_TYPE = "read"
_SYNC_ACTIVITY_LIMIT = 1000
_SYNC_ORDER_LOOKBACK_DAYS = 365
_CASH_SYMBOLS = frozenset({"CASH", "FCASH", "FDRXX", "SPAXX"})
_SYMBOL_PATTERN = re.compile(r"^[A-Z][A-Z0-9.-]{0,24}$")
_CASH_RECONCILIATION_TOLERANCE = Decimal("1.00")


class SnapTradeConfigurationError(RuntimeError):
    """Raised when SnapTrade cannot be used because configuration is missing."""


class SnapTradeIntegrationError(RuntimeError):
    """Raised for sanitized SnapTrade API failures."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 502,
        error_payload: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_payload = error_payload or {"detail": message}


@dataclass(slots=True)
class SnapTradeConfig:
    client_id: str
    consumer_key: str
    redirect_uri: str | None
    default_broker: str | None


@dataclass(slots=True)
class SnapTradeUser:
    user_id: str
    user_secret: str


@dataclass(slots=True)
class SnapTradeAccountKind:
    portfolio_account_type: str
    household_asset_group: str
    household_source_type: str
    household_account_type: str


@dataclass(slots=True)
class SnapTradeNormalizedAccount:
    account_id: str
    authorization_id: str | None
    name: str
    institution_name: str | None
    account_mask: str | None
    raw_type: str | None
    portfolio_account_type: str
    balance: Decimal | None
    cash_balance: Decimal | None
    currency: str | None
    household_account_id: str
    portfolio_account_id: str
    metadata: dict[str, object]


@dataclass(slots=True)
class SnapTradeNormalizedPosition:
    position_key: str
    symbol: str
    raw_symbol: str | None
    security_id: str | None
    security_kind: str | None
    units: Decimal
    price: Decimal | None
    average_purchase_price: Decimal | None
    market_value: Decimal | None
    cost_basis: Decimal | None
    currency: str | None
    metadata: dict[str, object]


@dataclass(slots=True)
class SnapTradeNormalizedOrder:
    brokerage_order_id: str
    status: str | None
    action: str | None
    symbol: str | None
    raw_symbol: str | None
    filled_quantity: Decimal | None
    execution_price: Decimal | None
    order_type: str | None
    time_in_force: str | None
    time_placed: datetime | None
    time_updated: datetime | None
    time_executed: datetime | None
    currency: str | None
    metadata: dict[str, object]


class SnapTradeReadOnlyClient:
    """Expose only the SnapTrade SDK surfaces this integration is allowed to use."""

    def __init__(self, client: object) -> None:
        self.api_status = client.api_status
        self.authentication = client.authentication
        self.connections = client.connections
        self.account_information = client.account_information

    def __getattr__(self, name: str) -> object:
        if name in {"trading", "options"}:
            raise AttributeError("SnapTrade trading APIs are disabled in portfolio-ai.")
        raise AttributeError(name)


def _now() -> datetime:
    return datetime.now(UTC)


def _json(value: object) -> str:
    return json.dumps(value, default=str)


def _is_unset(value: object) -> bool:
    return value.__class__.__name__.lower() == "unset"


def _plain(value: object) -> object:
    if _is_unset(value):
        converted: object = None
    elif value is None or isinstance(value, str | int | float | bool):
        converted = value
    elif isinstance(value, Decimal):
        converted = str(value)
    elif isinstance(value, datetime | date):
        converted = value.isoformat()
    elif isinstance(value, Mapping):
        converted = {
            str(key): converted
            for key, nested in value.items()
            if (converted := _plain(nested)) is not None
        }
    elif isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        converted = [converted for nested in value if (converted := _plain(nested)) is not None]
    elif callable(to_dict := getattr(value, "to_dict", None)):
        try:
            converted = _plain(to_dict())
        except Exception:
            converted = str(value)
    else:
        converted = str(value)
    return converted


def _body(response: object) -> object:
    return _plain(getattr(response, "body", response))


def _dict(value: object) -> dict[str, object]:
    plain = _plain(value)
    return cast(dict[str, object], plain) if isinstance(plain, dict) else {}


def _list(value: object) -> list[object]:
    plain = _plain(value)
    return cast(list[object], plain) if isinstance(plain, list) else []


def _string(value: object) -> str | None:
    if value is None or _is_unset(value):
        return None
    text = str(value).strip()
    return text or None


def _decimal(value: object) -> Decimal | None:
    if value is None or _is_unset(value):
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, ValueError):
        return None


def _number(value: object) -> Decimal | None:
    parsed = _decimal(value)
    return parsed if parsed is not None else None


def _coerce_timestamp(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    text = _string(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _redact_account_number(value: object) -> str | None:
    text = _string(value)
    if not text:
        return None
    if "*" in text:
        suffix = re.sub(r"[^A-Za-z0-9]", "", text.split("*")[-1])
        return suffix[-4:] if suffix else None
    compact = re.sub(r"[^A-Za-z0-9]", "", text)
    if not compact:
        return None
    return compact if len(compact) <= 4 else compact[-4:]


def _currency_code(value: object) -> str | None:
    if isinstance(value, Mapping):
        for key in ("code", "currency", "symbol"):
            if code := _string(value.get(key)):
                return code.upper()[:8]
    code = _string(value)
    return code.upper()[:8] if code else None


def _symbol(value: object) -> str | None:
    text = _string(value)
    if not text:
        return None
    normalized = text.replace("*", "").strip().upper()
    if normalized in _CASH_SYMBOLS:
        return None
    if not _SYMBOL_PATTERN.fullmatch(normalized):
        return None
    return normalized


def _snaptrade_error_payload(exc: ApiException) -> dict[str, object]:
    body = _dict(getattr(exc, "body", None))
    message = (
        _string(body.get("detail"))
        or _string(body.get("message"))
        or _string(body.get("error"))
        or _string(getattr(exc, "reason", None))
        or "SnapTrade request failed."
    )
    lower_message = message.lower()
    if any(
        secret_word in lower_message
        for secret_word in ("clientid", "client id", "consumer", "signature")
    ):
        message = "SnapTrade rejected the configured credentials."
    return {
        "error_type": "SNAPTRADE_API_ERROR",
        "error_code": _string(body.get("code")) or str(getattr(exc, "status", "") or "unknown"),
        "error_message": message,
        "status": int(getattr(exc, "status", 502) or 502),
    }


def _connection_portal_kwargs(
    *,
    user: SnapTradeUser,
    broker: str | None,
    redirect_uri: str | None,
) -> dict[str, object]:
    kwargs: dict[str, object] = {
        "user_id": user.user_id,
        "user_secret": user.user_secret,
        "show_close_button": True,
        "connection_type": _READ_ONLY_CONNECTION_TYPE,
    }
    if broker:
        kwargs["broker"] = broker
    if redirect_uri:
        kwargs["custom_redirect"] = redirect_uri
    return kwargs


def _brokerage_fields(connection: dict[str, object]) -> tuple[str | None, str | None]:
    brokerage = _dict(connection.get("brokerage"))
    name = _string(brokerage.get("name")) or _string(connection.get("brokerage_name"))
    slug = (
        _string(brokerage.get("slug"))
        or _string(brokerage.get("id"))
        or _string(connection.get("brokerage_slug"))
    )
    return name, slug


def _account_kind(*values: object) -> SnapTradeAccountKind:
    normalized = " ".join(value.lower() for raw in values if (value := _string(raw)))
    if "roth" in normalized:
        return SnapTradeAccountKind("Roth", "retirement", "retirement", "roth_ira")
    if "401" in normalized:
        return SnapTradeAccountKind("401k", "retirement", "retirement", "401k")
    if "hsa" in normalized:
        return SnapTradeAccountKind("HSA", "retirement", "retirement", "hsa")
    if any(token in normalized for token in ("ira", "rollover", "traditional")):
        return SnapTradeAccountKind("IRA", "retirement", "retirement", "ira")
    return SnapTradeAccountKind("Taxable", "taxable", "brokerage", "brokerage")


class SnapTradeService:
    """Configure SnapTrade and sync read-only brokerage data."""

    def __init__(
        self,
        *,
        storage: PortfolioStorage | None = None,
        client_factory: Callable[..., object] = SnapTrade,
    ) -> None:
        self.storage = storage or get_storage()
        self.cipher = CredentialCipher()
        self._client_factory = client_factory

    def get_status(self) -> dict[str, object]:
        with self.storage.connection() as conn:
            credential_rows = conn.execute(
                """
                SELECT field, value, updated_at
                FROM source_credentials
                WHERE source_id = %s
                """,
                [_SNAPTRADE_SOURCE_ID],
            ).fetchall()
            user_count = conn.execute(
                "SELECT COUNT(*) FROM snaptrade_users WHERE status = 'active'"
            ).fetchone()
            connection_count = conn.execute("SELECT COUNT(*) FROM snaptrade_connections").fetchone()
            source_account_count = conn.execute("SELECT COUNT(*) FROM snaptrade_accounts").fetchone()
            account_count = conn.execute(
                """
                SELECT COUNT(*)
                FROM (
                    SELECT DISTINCT COALESCE(
                        portfolio_account_id,
                        household_account_id::text,
                        account_id
                    ) AS display_account_id
                    FROM snaptrade_accounts
                ) display_accounts
                """
            ).fetchone()
            position_count = conn.execute("SELECT COUNT(*) FROM snaptrade_positions").fetchone()
            activity_count = conn.execute("SELECT COUNT(*) FROM snaptrade_activities").fetchone()
            order_count = conn.execute("SELECT COUNT(*) FROM snaptrade_orders").fetchone()
            latest_sync = conn.execute(
                "SELECT MAX(last_successful_sync_at) FROM snaptrade_users WHERE status = 'active'"
            ).fetchone()
            connection_rows = conn.execute(
                """
                SELECT authorization_id, brokerage_name, brokerage_slug, connection_type,
                       disabled, last_synced_at, owner_is_spouse, owner_name
                FROM snaptrade_connections
                ORDER BY updated_at DESC
                LIMIT 20
                """
            ).fetchall()
            account_rows = conn.execute(
                """
                WITH ranked_accounts AS (
                    SELECT
                        account_id,
                        name,
                        institution_name,
                        account_mask,
                        portfolio_account_type,
                        balance,
                        cash_balance,
                        currency,
                        last_synced_at,
                        ROW_NUMBER() OVER (
                            PARTITION BY COALESCE(
                                portfolio_account_id,
                                household_account_id::text,
                                account_id
                            )
                            ORDER BY last_synced_at DESC, account_id
                        ) AS row_rank
                    FROM snaptrade_accounts
                )
                SELECT account_id, name, institution_name, account_mask, portfolio_account_type,
                       balance, cash_balance, currency, last_synced_at
                FROM ranked_accounts
                WHERE row_rank = 1
                ORDER BY last_synced_at DESC, name
                LIMIT 20
                """
            ).fetchall()
            position_rows = conn.execute(
                "SELECT account_id, symbol, units, price FROM snaptrade_positions"
            ).fetchall()
            last_error = conn.execute(
                """
                SELECT last_error
                FROM snaptrade_users
                WHERE status = 'active' AND last_error IS NOT NULL
                ORDER BY updated_at DESC
                LIMIT 1
                """
            ).fetchone()

        raw_credentials = {str(row[0]): str(row[1]) for row in credential_rows}
        credential_updated_at = [
            row[2]
            for row in credential_rows
            if str(row[0]) in {"client_id", "consumer_key"}
            and row[1]
            and isinstance(row[2], datetime)
        ]
        client_id_configured = bool(raw_credentials.get("client_id"))
        consumer_key_configured = bool(raw_credentials.get("consumer_key"))
        configured = client_id_configured and consumer_key_configured

        # Re-value each account to current market price rather than displaying the
        # broker's last-synced total. We anchor on the broker total and apply only
        # the live price drift on holdings we can quote (double-count safe).
        positions_by_account: dict[str, list[tuple[float, float | None, str]]] = {}
        symbols: set[str] = set()
        for prow in position_rows:
            acct_id = str(prow[0])
            symbol = str(prow[1])
            units = float(prow[2]) if prow[2] is not None else 0.0
            broker_price = float(prow[3]) if prow[3] is not None else None
            positions_by_account.setdefault(acct_id, []).append((units, broker_price, symbol))
            symbols.add(symbol)

        price_data: dict[str, PriceData] = {}
        if symbols:
            price_data = PriceDataFetcher(self.storage).fetch_price_data(sorted(symbols))

        valuations = {
            str(row[0]): mark_to_market_account_value(
                row[5], positions_by_account.get(str(row[0]), []), price_data
            )
            for row in account_rows
        }
        return {
            "configured": configured,
            "client_id_configured": client_id_configured,
            "consumer_key_configured": consumer_key_configured,
            "configuration_updated_at": max(credential_updated_at).isoformat()
            if credential_updated_at
            else None,
            "encryption_ready": self.cipher.available,
            "access_mode": "read_only",
            "default_broker": raw_credentials.get("default_broker") or _DEFAULT_BROKER,
            "redirect_uri": raw_credentials.get("redirect_uri") or None,
            "user_registered": int(user_count[0] or 0) > 0 if user_count else False,
            "connection_count": int(connection_count[0] or 0) if connection_count else 0,
            "account_count": int(account_count[0] or 0) if account_count else 0,
            "source_account_count": int(source_account_count[0] or 0) if source_account_count else 0,
            "position_count": int(position_count[0] or 0) if position_count else 0,
            "activity_count": int(activity_count[0] or 0) if activity_count else 0,
            "order_count": int(order_count[0] or 0) if order_count else 0,
            "last_successful_sync_at": latest_sync[0].isoformat()
            if latest_sync and isinstance(latest_sync[0], datetime)
            else None,
            "last_error": str(last_error[0]) if last_error and last_error[0] else None,
            "connections": [
                {
                    "authorization_id": str(row[0]),
                    "brokerage_name": str(row[1]) if row[1] else None,
                    "brokerage_slug": str(row[2]) if row[2] else None,
                    "connection_type": str(row[3]),
                    "disabled": bool(row[4]),
                    "last_synced_at": row[5].isoformat() if isinstance(row[5], datetime) else None,
                    "owner_is_spouse": bool(row[6]),
                    "owner_name": str(row[7]) if row[7] else None,
                }
                for row in connection_rows
            ],
            "accounts": [
                {
                    "account_id": str(row[0]),
                    "name": str(row[1]),
                    "institution_name": str(row[2]) if row[2] else None,
                    "account_mask": str(row[3]) if row[3] else None,
                    "portfolio_account_type": str(row[4]),
                    "balance": float(row[5]) if row[5] is not None else None,
                    "market_value": valuations[str(row[0])].total_value,
                    "valuation_source": valuations[str(row[0])].valuation_source,
                    "quote_as_of": (
                        valuations[str(row[0])].quote_as_of.isoformat()
                        if valuations[str(row[0])].quote_as_of is not None
                        else None
                    ),
                    "cash_balance": float(row[6]) if row[6] is not None else None,
                    "currency": str(row[7]) if row[7] else None,
                    "last_synced_at": row[8].isoformat() if isinstance(row[8], datetime) else None,
                }
                for row in account_rows
            ],
        }

    def get_orders(
        self,
        *,
        account_id: str | None = None,
        limit: int = 50,
    ) -> dict[str, object]:
        clean_account_id = account_id.strip() if account_id else None
        clean_limit = max(1, min(int(limit), 200))
        params: list[object] = []
        where_clause = ""
        if clean_account_id:
            where_clause = "WHERE o.account_id = %s"
            params.append(clean_account_id)
        params.append(clean_limit)

        with self.storage.connection() as conn:
            rows = conn.execute(
                f"""
                SELECT
                    o.account_id,
                    a.name,
                    a.institution_name,
                    a.account_mask,
                    o.brokerage_order_id,
                    o.status,
                    o.action,
                    o.symbol,
                    o.raw_symbol,
                    o.filled_quantity,
                    o.execution_price,
                    o.order_type,
                    o.time_in_force,
                    o.time_placed,
                    o.time_updated,
                    o.time_executed,
                    o.currency,
                    o.last_synced_at
                FROM snaptrade_orders o
                JOIN snaptrade_accounts a ON a.account_id = o.account_id
                {where_clause}
                ORDER BY COALESCE(o.time_executed, o.time_updated, o.time_placed) DESC NULLS LAST,
                         o.last_synced_at DESC
                LIMIT %s
                """,
                params,
            ).fetchall()

        return {
            "orders": [
                {
                    "account_id": str(row[0]),
                    "account_name": str(row[1]) if row[1] else None,
                    "institution_name": str(row[2]) if row[2] else None,
                    "account_mask": str(row[3]) if row[3] else None,
                    "brokerage_order_id": str(row[4]),
                    "status": str(row[5]) if row[5] else None,
                    "action": str(row[6]) if row[6] else None,
                    "symbol": str(row[7]) if row[7] else None,
                    "raw_symbol": str(row[8]) if row[8] else None,
                    "filled_quantity": float(row[9]) if row[9] is not None else None,
                    "execution_price": float(row[10]) if row[10] is not None else None,
                    "order_type": str(row[11]) if row[11] else None,
                    "time_in_force": str(row[12]) if row[12] else None,
                    "time_placed": row[13].isoformat() if isinstance(row[13], datetime) else None,
                    "time_updated": row[14].isoformat() if isinstance(row[14], datetime) else None,
                    "time_executed": row[15].isoformat()
                    if isinstance(row[15], datetime)
                    else None,
                    "currency": str(row[16]) if row[16] else None,
                    "last_synced_at": row[17].isoformat()
                    if isinstance(row[17], datetime)
                    else None,
                }
                for row in rows
            ],
        }

    def configure(
        self,
        *,
        client_id: str | None,
        consumer_key: str | None,
        redirect_uri: str | None = None,
        default_broker: str | None = _DEFAULT_BROKER,
    ) -> dict[str, object]:
        if not self.cipher.available:
            raise SecretKeyUnavailableError(
                "PORTFOLIO_SECRET_KEY is required for encrypted credentials"
            )
        client_id = client_id.strip() if client_id else ""
        consumer_key = consumer_key.strip() if consumer_key else ""
        existing_credentials = get_source_credentials(self.storage, _SNAPTRADE_SOURCE_ID)
        existing_client_id = existing_credentials.get("client_id")
        existing_consumer_key = existing_credentials.get("consumer_key")
        if (not client_id or not consumer_key) and (
            not (client_id or existing_client_id) or not (consumer_key or existing_consumer_key)
        ):
            raise SnapTradeConfigurationError("SnapTrade client_id and consumer_key are required.")
        broker = (default_broker or "").strip().upper() or _DEFAULT_BROKER
        self._ensure_source_registry()
        if client_id:
            set_source_credential(self.storage, _SNAPTRADE_SOURCE_ID, "client_id", client_id)
        if consumer_key:
            set_source_credential(
                self.storage,
                _SNAPTRADE_SOURCE_ID,
                "consumer_key",
                consumer_key,
            )
        set_source_credential(
            self.storage,
            _SNAPTRADE_SOURCE_ID,
            "redirect_uri",
            redirect_uri.strip() if redirect_uri else "",
            encrypt=False,
        )
        set_source_credential(
            self.storage,
            _SNAPTRADE_SOURCE_ID,
            "default_broker",
            broker,
            encrypt=False,
        )
        logger.info("snaptrade_source_credentials_saved", broker=broker)
        return self.get_status()

    def create_connection_portal(self, *, broker: str | None = None) -> dict[str, object]:
        config = self._load_config()
        client = self._client(config)
        user = self._ensure_user(client)
        login_broker = (broker or config.default_broker or "").strip().upper() or None
        try:
            response = _dict(
                _body(
                    client.authentication.login_snap_trade_user(
                        **_connection_portal_kwargs(
                            user=user,
                            broker=login_broker,
                            redirect_uri=config.redirect_uri,
                        )
                    )
                )
            )
        except ApiException as exc:
            payload = _snaptrade_error_payload(exc)
            raise SnapTradeIntegrationError(
                str(payload["error_message"]),
                status_code=502,
                error_payload=payload,
            ) from exc

        portal_url = (
            _string(response.get("redirectURI"))
            or _string(response.get("redirect_uri"))
            or _string(response.get("url"))
        )
        if not portal_url:
            raise SnapTradeIntegrationError("SnapTrade did not return a connection portal URL.")
        return {
            "portal_url": portal_url,
            "session_id": _string(response.get("sessionId")),
            "broker": login_broker,
            "access_mode": "read_only",
            "expires_in_minutes": 5,
        }

    def sync(self) -> dict[str, object]:
        config = self._load_config()
        client = self._client(config)
        user = self._load_user()
        totals: dict[str, object] = {
            "connection_count": 0,
            "account_count": 0,
            "position_count": 0,
            "activity_count": 0,
            "order_count": 0,
            "portfolio_account_count": 0,
            "portfolio_position_count": 0,
            "errors": [],
        }
        symbols: set[str] = set()
        try:
            connections = _list(
                _body(
                    client.connections.list_brokerage_authorizations(
                        user_id=user.user_id,
                        user_secret=user.user_secret,
                    )
                )
            )
        except ApiException as exc:
            payload = _snaptrade_error_payload(exc)
            self._record_user_error(user.user_id, str(payload["error_message"]))
            raise SnapTradeIntegrationError(
                str(payload["error_message"]),
                status_code=502,
                error_payload=payload,
            ) from exc

        for raw_connection in connections:
            connection = _dict(raw_connection)
            authorization_id = _string(connection.get("id"))
            if not authorization_id:
                continue
            self._upsert_connection(
                user_id=user.user_id, authorization_id=authorization_id, connection=connection
            )
            totals["connection_count"] = int(totals["connection_count"]) + 1
            try:
                accounts = _list(
                    _body(
                        client.connections.list_brokerage_authorization_accounts(
                            authorization_id=authorization_id,
                            user_id=user.user_id,
                            user_secret=user.user_secret,
                        )
                    )
                )
            except ApiException as exc:
                payload = _snaptrade_error_payload(exc)
                errors = totals["errors"]
                if isinstance(errors, list):
                    errors.append({"authorization_id": authorization_id, **payload})
                continue
            for raw_account in accounts:
                raw_account_dict = _dict(raw_account)
                account_id = _string(raw_account_dict.get("id"))
                direct_cash_balance: Decimal | None = None
                direct_cash_currency: str | None = None
                if account_id:
                    try:
                        direct_cash_balance, direct_cash_currency = self._account_cash_balance(
                            _list(
                                _body(
                                    client.account_information.get_user_account_balance(
                                        account_id=account_id,
                                        user_id=user.user_id,
                                        user_secret=user.user_secret,
                                    )
                                )
                            ),
                            preferred_currency=self._account_balance(raw_account_dict)[1],
                        )
                    except ApiException as exc:
                        payload = _snaptrade_error_payload(exc)
                        errors = totals["errors"]
                        if isinstance(errors, list):
                            errors.append(
                                {"account_id": account_id, "surface": "balances", **payload}
                            )
                account = self._sync_account(
                    user=user,
                    raw_account=raw_account_dict,
                    authorization_id=authorization_id,
                    cash_balance=direct_cash_balance,
                    cash_currency=direct_cash_currency,
                )
                if account is None:
                    continue
                totals["account_count"] = int(totals["account_count"]) + 1
                totals["portfolio_account_count"] = int(totals["portfolio_account_count"]) + 1
                try:
                    position_count, position_symbols = self._sync_positions(
                        client=client,
                        user=user,
                        account=account,
                    )
                    activity_count = self._sync_activities(
                        client=client,
                        user=user,
                        account_id=account.account_id,
                    )
                    order_count = self._sync_orders(
                        client=client,
                        user=user,
                        account_id=account.account_id,
                    )
                except ApiException as exc:
                    payload = _snaptrade_error_payload(exc)
                    errors = totals["errors"]
                    if isinstance(errors, list):
                        errors.append({"account_id": account.account_id, **payload})
                    continue
                totals["position_count"] = int(totals["position_count"]) + position_count
                totals["portfolio_position_count"] = (
                    int(totals["portfolio_position_count"]) + position_count
                )
                totals["activity_count"] = int(totals["activity_count"]) + activity_count
                totals["order_count"] = int(totals["order_count"]) + order_count
                symbols.update(position_symbols)

        self._reconcile_account_ownership()
        self._record_user_sync(user.user_id, has_errors=bool(totals["errors"]))
        ensure_symbols_in_watchlist(self.storage, sorted(symbols), source="snaptrade")
        return totals

    def _reconcile_account_ownership(self) -> None:
        """Derive ``portfolio_accounts.is_spouse`` from connection ownership.

        An account is spouse-owned only when *every* connection that surfaces
        it is spouse-owned (``bool_and``). A joint account visible under both
        spouses' logins therefore stays attributed to the household
        (``is_spouse = false``), never to one person. This is purely an
        attribution label: it does not gate any balance, net-worth, or
        retirement-projection total, all of which include every account.
        """
        with self.storage.connection() as conn:
            conn.execute(
                """
                UPDATE portfolio_accounts pa
                SET is_spouse = sub.all_spouse,
                    updated_at = %s
                FROM (
                    SELECT sa.portfolio_account_id AS portfolio_account_id,
                           bool_and(COALESCE(c.owner_is_spouse, FALSE)) AS all_spouse
                    FROM snaptrade_accounts sa
                    JOIN snaptrade_connections c
                        ON c.authorization_id = sa.authorization_id
                    WHERE sa.portfolio_account_id IS NOT NULL
                    GROUP BY sa.portfolio_account_id
                ) sub
                WHERE pa.id = sub.portfolio_account_id
                  AND pa.is_spouse IS DISTINCT FROM sub.all_spouse
                """,
                [_now()],
            )
            conn.commit()

    def set_connection_owner(
        self,
        authorization_id: str,
        *,
        is_spouse: bool,
        owner_name: str | None = None,
    ) -> dict[str, object]:
        """Set who owns a brokerage connection, then re-derive attribution.

        Persists to ``snaptrade_connections`` (columns the sync upsert never
        overwrites, so the choice survives re-syncs) and immediately
        reconciles ``portfolio_accounts.is_spouse``.
        """
        clean_name = (owner_name or "").strip() or None
        with self.storage.connection() as conn:
            updated = conn.execute(
                """
                UPDATE snaptrade_connections
                SET owner_is_spouse = %s,
                    owner_name = %s,
                    updated_at = %s
                WHERE authorization_id = %s
                """,
                [bool(is_spouse), clean_name, _now(), authorization_id],
            ).rowcount
            conn.commit()
        if not updated:
            raise SnapTradeIntegrationError(
                "Unknown brokerage connection.", status_code=404
            )
        self._reconcile_account_ownership()
        return {
            "authorization_id": authorization_id,
            "owner_is_spouse": bool(is_spouse),
            "owner_name": clean_name,
        }

    def _ensure_source_registry(self) -> None:
        with self.storage.connection() as conn:
            conn.execute(
                """
                INSERT INTO source_registry (
                    source_id, display_name, priority, enabled, definition, created_at, updated_at
                ) VALUES (
                    %s, 'SnapTrade', 55, TRUE,
                    %s::jsonb,
                    CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP
                )
                ON CONFLICT (source_id) DO UPDATE SET
                    display_name = EXCLUDED.display_name,
                    enabled = TRUE,
                    definition = source_registry.definition || EXCLUDED.definition,
                    updated_at = CURRENT_TIMESTAMP
                """,
                [
                    _SNAPTRADE_SOURCE_ID,
                    _json(
                        {
                            "category": "household_investments",
                            "credential_store": "source_credentials",
                            "access_mode": "read_only",
                        }
                    ),
                ],
            )
            conn.commit()

    def _load_config(self) -> SnapTradeConfig:
        if not self.cipher.available:
            raise SecretKeyUnavailableError(
                "PORTFOLIO_SECRET_KEY is required for encrypted credentials"
            )
        credentials = get_source_credentials(self.storage, _SNAPTRADE_SOURCE_ID)
        client_id = credentials.get("client_id")
        consumer_key = credentials.get("consumer_key")
        if not client_id or not consumer_key:
            raise SnapTradeConfigurationError("SnapTrade credentials are not configured.")
        return SnapTradeConfig(
            client_id=client_id,
            consumer_key=consumer_key,
            redirect_uri=credentials.get("redirect_uri") or None,
            default_broker=(credentials.get("default_broker") or _DEFAULT_BROKER).upper(),
        )

    def _client(self, config: SnapTradeConfig) -> SnapTradeReadOnlyClient:
        return SnapTradeReadOnlyClient(
            self._client_factory(client_id=config.client_id, consumer_key=config.consumer_key)
        )

    def _ensure_user(self, client: SnapTradeReadOnlyClient) -> SnapTradeUser:
        existing = self._load_user(required=False)
        if existing is not None:
            return existing
        user_id = f"portfolio-ai-{uuid.uuid4()}"
        try:
            response = _dict(_body(client.authentication.register_snap_trade_user(user_id=user_id)))
        except ApiException as exc:
            payload = _snaptrade_error_payload(exc)
            raise SnapTradeIntegrationError(
                str(payload["error_message"]),
                status_code=502,
                error_payload=payload,
            ) from exc
        registered_user_id = _string(response.get("userId")) or user_id
        user_secret = _string(response.get("userSecret"))
        if not user_secret:
            raise SnapTradeIntegrationError("SnapTrade did not return a user secret.")
        with self.storage.connection() as conn:
            conn.execute(
                """
                INSERT INTO snaptrade_users (
                    id, user_id, user_secret_ciphertext, status, metadata, created_at, updated_at
                ) VALUES (%s, %s, %s, 'active', %s::jsonb, %s, %s)
                ON CONFLICT (user_id) DO UPDATE SET
                    user_secret_ciphertext = EXCLUDED.user_secret_ciphertext,
                    status = 'active',
                    metadata = snaptrade_users.metadata || EXCLUDED.metadata,
                    updated_at = EXCLUDED.updated_at
                """,
                [
                    str(uuid.uuid4()),
                    registered_user_id,
                    self.cipher.encrypt(user_secret),
                    _json({"source": "snaptrade"}),
                    _now(),
                    _now(),
                ],
            )
            conn.commit()
        logger.info("snaptrade_user_registered", user_id=registered_user_id)
        return SnapTradeUser(user_id=registered_user_id, user_secret=user_secret)

    def _load_user(self, *, required: bool = True) -> SnapTradeUser | None:
        with self.storage.connection() as conn:
            row = conn.execute(
                """
                SELECT user_id, user_secret_ciphertext
                FROM snaptrade_users
                WHERE status = 'active'
                ORDER BY created_at DESC
                LIMIT 1
                """
            ).fetchone()
        if row is None:
            if required:
                raise SnapTradeConfigurationError("Create a SnapTrade connection portal first.")
            return None
        try:
            user_secret = self.cipher.decrypt(str(row[1]))
        except (SecretDecryptionError, SecretKeyUnavailableError):
            raise
        return SnapTradeUser(user_id=str(row[0]), user_secret=user_secret)

    def _upsert_connection(
        self,
        *,
        user_id: str,
        authorization_id: str,
        connection: dict[str, object],
    ) -> None:
        brokerage_name, brokerage_slug = _brokerage_fields(connection)
        synced_at = _now()
        with self.storage.connection() as conn:
            conn.execute(
                """
                INSERT INTO snaptrade_connections (
                    id, user_id, authorization_id, brokerage_name, brokerage_slug,
                    connection_name, connection_type, disabled, disabled_date, metadata,
                    last_synced_at, created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s
                )
                ON CONFLICT (authorization_id) DO UPDATE SET
                    brokerage_name = EXCLUDED.brokerage_name,
                    brokerage_slug = EXCLUDED.brokerage_slug,
                    connection_name = EXCLUDED.connection_name,
                    connection_type = EXCLUDED.connection_type,
                    disabled = EXCLUDED.disabled,
                    disabled_date = EXCLUDED.disabled_date,
                    metadata = EXCLUDED.metadata,
                    last_synced_at = EXCLUDED.last_synced_at,
                    updated_at = EXCLUDED.updated_at
                """,
                [
                    str(uuid.uuid4()),
                    user_id,
                    authorization_id,
                    brokerage_name,
                    brokerage_slug,
                    _string(connection.get("name")),
                    _string(connection.get("type")) or _READ_ONLY_CONNECTION_TYPE,
                    bool(connection.get("disabled") or False),
                    _coerce_timestamp(connection.get("disabled_date")),
                    _json(connection),
                    synced_at,
                    synced_at,
                    synced_at,
                ],
            )
            conn.commit()

    def _sync_account(
        self,
        *,
        user: SnapTradeUser,
        raw_account: dict[str, object],
        authorization_id: str,
        cash_balance: Decimal | None = None,
        cash_currency: str | None = None,
    ) -> SnapTradeNormalizedAccount | None:
        account_id = _string(raw_account.get("id"))
        if not account_id:
            return None
        name = _string(raw_account.get("name")) or "SnapTrade account"
        institution_name = _string(raw_account.get("institution_name"))
        raw_type = _string(_dict(raw_account.get("meta")).get("type")) or _string(
            raw_account.get("type")
        )
        account_mask = _redact_account_number(raw_account.get("number"))
        kind = _account_kind(name, raw_type)
        balance, currency = self._account_balance(raw_account)
        cash_balance = (
            cash_balance if cash_balance is not None else self._cash_balance_from_account(raw_account)
        )
        currency = currency or cash_currency
        sanitized_metadata = dict(raw_account)
        sanitized_metadata["number"] = account_mask
        with self.storage.connection() as conn:
            household_account_id = self._resolve_household_account(
                conn=conn,
                account_id=account_id,
                label=self._account_label(institution_name, name, account_mask),
                name=name,
                kind=kind,
                institution_name=institution_name,
                account_mask=account_mask,
            )
            portfolio_account_id = self._resolve_portfolio_account(
                conn=conn,
                account_id=account_id,
                name=name,
                portfolio_account_type=kind.portfolio_account_type,
                household_account_id=household_account_id,
                cash_balance=None,
            )
            synced_at = _now()
            conn.execute(
                """
                INSERT INTO snaptrade_accounts (
                    id, user_id, authorization_id, account_id, portfolio_account_id,
                    household_account_id, name, institution_name, account_mask, raw_type,
                    portfolio_account_type, balance, cash_balance, currency, metadata,
                    last_synced_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s::jsonb, %s
                )
                ON CONFLICT (account_id) DO UPDATE SET
                    user_id = EXCLUDED.user_id,
                    authorization_id = EXCLUDED.authorization_id,
                    portfolio_account_id = EXCLUDED.portfolio_account_id,
                    household_account_id = EXCLUDED.household_account_id,
                    name = EXCLUDED.name,
                    institution_name = EXCLUDED.institution_name,
                    account_mask = EXCLUDED.account_mask,
                    raw_type = EXCLUDED.raw_type,
                    portfolio_account_type = EXCLUDED.portfolio_account_type,
                    balance = EXCLUDED.balance,
                    currency = EXCLUDED.currency,
                    metadata = EXCLUDED.metadata,
                    last_synced_at = EXCLUDED.last_synced_at
                """,
                [
                    str(uuid.uuid4()),
                    user.user_id,
                    authorization_id,
                    account_id,
                    portfolio_account_id,
                    household_account_id,
                    name,
                    institution_name,
                    account_mask,
                    raw_type,
                    kind.portfolio_account_type,
                    balance,
                    None,
                    currency,
                    _json(sanitized_metadata),
                    synced_at,
                ],
            )
            conn.commit()
        return SnapTradeNormalizedAccount(
            account_id=account_id,
            authorization_id=authorization_id,
            name=name,
            institution_name=institution_name,
            account_mask=account_mask,
            raw_type=raw_type,
            portfolio_account_type=kind.portfolio_account_type,
            balance=balance,
            cash_balance=cash_balance,
            currency=currency,
            household_account_id=household_account_id,
            portfolio_account_id=portfolio_account_id,
            metadata=sanitized_metadata,
        )

    def _sync_positions(
        self,
        *,
        client: SnapTradeReadOnlyClient,
        user: SnapTradeUser,
        account: SnapTradeNormalizedAccount,
    ) -> tuple[int, set[str]]:
        response = _dict(
            _body(
                client.account_information.get_all_account_positions(
                    account_id=account.account_id,
                    user_id=user.user_id,
                    user_secret=user.user_secret,
                )
            )
        )
        positions = [
            position
            for raw_position in _list(response.get("results"))
            if (position := self._normalize_position(_dict(raw_position))) is not None
        ]
        synced_at = _now()
        symbols = {position.symbol for position in positions}
        with self.storage.connection() as conn:
            existing_rows = conn.execute(
                """
                SELECT position_key, portfolio_position_id
                FROM snaptrade_positions
                WHERE account_id = %s
                """,
                [account.account_id],
            ).fetchall()
            existing_portfolio_ids = {
                str(row[0]): str(row[1]) for row in existing_rows if row[1] is not None
            }
            desired_keys = {position.position_key for position in positions}
            if desired_keys:
                conn.execute(
                    """
                    DELETE FROM snaptrade_positions
                    WHERE account_id = %s AND position_key <> ALL(%s)
                    """,
                    [account.account_id, list(desired_keys)],
                )
            else:
                conn.execute(
                    "DELETE FROM snaptrade_positions WHERE account_id = %s",
                    [account.account_id],
                )
            self._replace_portfolio_positions(
                conn=conn,
                account=account,
                positions=positions,
                existing_portfolio_ids=existing_portfolio_ids,
                synced_at=synced_at,
            )
            self._update_portfolio_account_cash_balance(
                conn=conn,
                account=account,
                positions=positions,
                synced_at=synced_at,
            )
            for position in positions:
                portfolio_position_id = f"snaptrade:{account.account_id}:{position.position_key}"
                conn.execute(
                    """
                    INSERT INTO snaptrade_positions (
                        id, account_id, position_key, portfolio_position_id, symbol, raw_symbol,
                        security_id, security_kind, units, price, average_purchase_price,
                        market_value, cost_basis, currency, metadata, last_synced_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s::jsonb, %s
                    )
                    ON CONFLICT (account_id, position_key) DO UPDATE SET
                        portfolio_position_id = EXCLUDED.portfolio_position_id,
                        symbol = EXCLUDED.symbol,
                        raw_symbol = EXCLUDED.raw_symbol,
                        security_id = EXCLUDED.security_id,
                        security_kind = EXCLUDED.security_kind,
                        units = EXCLUDED.units,
                        price = EXCLUDED.price,
                        average_purchase_price = EXCLUDED.average_purchase_price,
                        market_value = EXCLUDED.market_value,
                        cost_basis = EXCLUDED.cost_basis,
                        currency = EXCLUDED.currency,
                        metadata = EXCLUDED.metadata,
                        last_synced_at = EXCLUDED.last_synced_at
                    """,
                    [
                        str(uuid.uuid4()),
                        account.account_id,
                        position.position_key,
                        portfolio_position_id,
                        position.symbol,
                        position.raw_symbol,
                        position.security_id,
                        position.security_kind,
                        position.units,
                        position.price,
                        position.average_purchase_price,
                        position.market_value,
                        position.cost_basis,
                        position.currency,
                        _json(position.metadata),
                        synced_at,
                    ],
                )
            conn.commit()
        return len(positions), symbols

    def _sync_activities(
        self,
        *,
        client: SnapTradeReadOnlyClient,
        user: SnapTradeUser,
        account_id: str,
    ) -> int:
        response = _dict(
            _body(
                client.account_information.get_account_activities(
                    account_id=account_id,
                    user_id=user.user_id,
                    user_secret=user.user_secret,
                    limit=_SYNC_ACTIVITY_LIMIT,
                )
            )
        )
        activities = [_dict(item) for item in _list(response.get("data"))]
        synced_at = _now()
        count = 0
        with self.storage.connection() as conn:
            for activity in activities:
                activity_id = _string(activity.get("id")) or _string(
                    activity.get("external_reference_id")
                )
                if not activity_id:
                    continue
                symbol = self._activity_symbol(activity)
                currency = _currency_code(activity.get("currency"))
                conn.execute(
                    """
                    INSERT INTO snaptrade_activities (
                        id, account_id, activity_id, activity_type, symbol, trade_date,
                        settlement_date, amount, units, price, fee, currency, description,
                        external_reference_id, metadata, last_synced_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s::jsonb, %s
                    )
                    ON CONFLICT (account_id, activity_id) DO UPDATE SET
                        account_id = EXCLUDED.account_id,
                        activity_type = EXCLUDED.activity_type,
                        symbol = EXCLUDED.symbol,
                        trade_date = EXCLUDED.trade_date,
                        settlement_date = EXCLUDED.settlement_date,
                        amount = EXCLUDED.amount,
                        units = EXCLUDED.units,
                        price = EXCLUDED.price,
                        fee = EXCLUDED.fee,
                        currency = EXCLUDED.currency,
                        description = EXCLUDED.description,
                        external_reference_id = EXCLUDED.external_reference_id,
                        metadata = EXCLUDED.metadata,
                        last_synced_at = EXCLUDED.last_synced_at
                    """,
                    [
                        str(uuid.uuid4()),
                        account_id,
                        activity_id,
                        _string(activity.get("type")),
                        symbol,
                        _coerce_timestamp(activity.get("trade_date")),
                        _coerce_timestamp(activity.get("settlement_date")),
                        _number(activity.get("amount")),
                        _number(activity.get("units")),
                        _number(activity.get("price")),
                        _number(activity.get("fee")),
                        currency,
                        _string(activity.get("description")),
                        _string(activity.get("external_reference_id")),
                        _json(activity),
                        synced_at,
                    ],
                )
                count += 1
            conn.commit()
        return count

    def _sync_orders(
        self,
        *,
        client: SnapTradeReadOnlyClient,
        user: SnapTradeUser,
        account_id: str,
    ) -> int:
        orders = [
            order
            for raw_order in _list(
                _body(
                    client.account_information.get_user_account_orders(
                        account_id=account_id,
                        user_id=user.user_id,
                        user_secret=user.user_secret,
                        state="all",
                        days=_SYNC_ORDER_LOOKBACK_DAYS,
                    )
                )
            )
            if (order := self._normalize_order(_dict(raw_order))) is not None
        ]
        synced_at = _now()
        with self.storage.connection() as conn:
            for order in orders:
                conn.execute(
                    """
                    INSERT INTO snaptrade_orders (
                        id, account_id, brokerage_order_id, status, action, symbol,
                        raw_symbol, filled_quantity, execution_price, order_type,
                        time_in_force, time_placed, time_updated, time_executed,
                        currency, metadata, last_synced_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s::jsonb, %s
                    )
                    ON CONFLICT (account_id, brokerage_order_id) DO UPDATE SET
                        status = EXCLUDED.status,
                        action = EXCLUDED.action,
                        symbol = EXCLUDED.symbol,
                        raw_symbol = EXCLUDED.raw_symbol,
                        filled_quantity = EXCLUDED.filled_quantity,
                        execution_price = EXCLUDED.execution_price,
                        order_type = EXCLUDED.order_type,
                        time_in_force = EXCLUDED.time_in_force,
                        time_placed = EXCLUDED.time_placed,
                        time_updated = EXCLUDED.time_updated,
                        time_executed = EXCLUDED.time_executed,
                        currency = EXCLUDED.currency,
                        metadata = EXCLUDED.metadata,
                        last_synced_at = EXCLUDED.last_synced_at
                    """,
                    [
                        str(uuid.uuid4()),
                        account_id,
                        order.brokerage_order_id,
                        order.status,
                        order.action,
                        order.symbol,
                        order.raw_symbol,
                        order.filled_quantity,
                        order.execution_price,
                        order.order_type,
                        order.time_in_force,
                        order.time_placed,
                        order.time_updated,
                        order.time_executed,
                        order.currency,
                        _json(order.metadata),
                        synced_at,
                    ],
                )
            conn.commit()
        return len(orders)

    def _resolve_household_account(
        self,
        *,
        conn: Any,
        account_id: str,
        label: str,
        name: str,
        kind: SnapTradeAccountKind,
        institution_name: str | None,
        account_mask: str | None,
    ) -> str:
        identity_key = f"snaptrade_account:{account_id}"
        mask_matched_household_account_id = (
            self._match_household_account_by_snaptrade_mask(
                conn=conn,
                institution_name=institution_name,
                account_mask=account_mask,
            )
            if institution_name and account_mask
            else None
        )
        row = conn.execute(
            """
            SELECT household_account_id
            FROM household_account_identities
            WHERE identity_key = %s
            LIMIT 1
            """,
            [identity_key],
        ).fetchone()
        if mask_matched_household_account_id is not None:
            household_account_id = mask_matched_household_account_id
            self._update_household_account_from_snaptrade(
                conn=conn,
                household_account_id=household_account_id,
                account_id=account_id,
                label=label,
                kind=kind,
                institution_name=institution_name,
                account_mask=account_mask,
            )
        elif (
            row is not None
            and row[0] is not None
            and (
                account_mask is None
                or self._household_account_accepts_snaptrade_mask(
                    conn=conn,
                    household_account_id=str(row[0]),
                    account_mask=account_mask,
                )
            )
        ):
            household_account_id = str(row[0])
            self._update_household_account_from_snaptrade(
                conn=conn,
                household_account_id=household_account_id,
                account_id=account_id,
                label=label,
                kind=kind,
                institution_name=institution_name,
                account_mask=account_mask,
            )
        else:
            household_account_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO household_accounts (
                    id, primary_identity_key, canonical_label, asset_group, account_type,
                    source_type, institution_name, account_mask, metadata, created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s
                )
                """,
                [
                    household_account_id,
                    identity_key,
                    label,
                    kind.household_asset_group,
                    kind.household_account_type,
                    kind.household_source_type,
                    institution_name,
                    account_mask,
                    _json({"snaptrade_account_id": account_id}),
                    _now(),
                    _now(),
                ],
            )

        conn.execute(
            """
            INSERT INTO household_account_identities (
                id, household_account_id, identity_key, identity_kind, is_primary,
                confidence, metadata, created_at, updated_at
            ) VALUES (
                %s, %s, %s, 'snaptrade_account', FALSE, 1.0, %s::jsonb, %s, %s
            )
            ON CONFLICT (identity_key) DO UPDATE SET
                household_account_id = EXCLUDED.household_account_id,
                confidence = 1.0,
                metadata = household_account_identities.metadata || EXCLUDED.metadata,
                updated_at = EXCLUDED.updated_at
            """,
            [
                str(uuid.uuid4()),
                household_account_id,
                identity_key,
                _json({"source": "snaptrade"}),
                _now(),
                _now(),
            ],
        )
        return household_account_id

    def _match_household_account_by_snaptrade_mask(
        self,
        *,
        conn: Any,
        institution_name: str | None,
        account_mask: str | None,
    ) -> str | None:
        if not institution_name or not account_mask:
            return None
        evidence_rows = conn.execute(
            """
            SELECT household_account_id, account_mask
            FROM household_evidence_accounts
            WHERE household_account_id IS NOT NULL
              AND lower(COALESCE(institution_name, '')) = lower(%s)
              AND account_mask IS NOT NULL
            ORDER BY updated_at DESC
            LIMIT 25
            """,
            [institution_name],
        ).fetchall()
        evidence_account_ids = [
            str(row[0])
            for row in evidence_rows
            if row[0] is not None and account_masks_match(row[1], account_mask)
        ]
        unique_evidence_account_ids = list(dict.fromkeys(evidence_account_ids))
        if len(unique_evidence_account_ids) == 1:
            return unique_evidence_account_ids[0]

        rows = conn.execute(
            """
            SELECT id, account_mask
            FROM household_accounts
            WHERE lower(COALESCE(institution_name, '')) = lower(%s)
              AND account_mask IS NOT NULL
            ORDER BY updated_at DESC
            LIMIT 25
            """,
            [institution_name],
        ).fetchall()
        for row in rows:
            if not account_masks_match(row[1], account_mask):
                continue
            household_account_id = str(row[0])
            if self._household_account_accepts_snaptrade_mask(
                conn=conn,
                household_account_id=household_account_id,
                account_mask=account_mask,
            ):
                return household_account_id
        return None

    @staticmethod
    def _household_account_accepts_snaptrade_mask(
        *,
        conn: Any,
        household_account_id: str,
        account_mask: str,
    ) -> bool:
        evidence_rows = conn.execute(
            """
            SELECT DISTINCT account_mask
            FROM household_evidence_accounts
            WHERE household_account_id = %s
              AND account_mask IS NOT NULL
            """,
            [household_account_id],
        ).fetchall()
        evidence_masks = [str(row[0]) for row in evidence_rows if row[0] is not None]
        if evidence_masks:
            return any(account_masks_match(mask, account_mask) for mask in evidence_masks)

        row = conn.execute(
            """
            SELECT account_mask
            FROM household_accounts
            WHERE id = %s
            """,
            [household_account_id],
        ).fetchone()
        if row is None or row[0] is None:
            return True
        existing_mask = str(row[0])
        return account_masks_match(existing_mask, account_mask)

    def _update_household_account_from_snaptrade(
        self,
        *,
        conn: Any,
        household_account_id: str,
        account_id: str,
        label: str,
        kind: SnapTradeAccountKind,
        institution_name: str | None,
        account_mask: str | None,
    ) -> None:
        conn.execute(
            """
            UPDATE household_accounts
            SET canonical_label = %s,
                asset_group = %s,
                account_type = %s,
                source_type = %s,
                institution_name = %s,
                account_mask = %s,
                metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb,
                updated_at = %s
            WHERE id = %s
            """,
            [
                label,
                kind.household_asset_group,
                kind.household_account_type,
                kind.household_source_type,
                institution_name,
                account_mask,
                _json({"snaptrade_account_id": account_id}),
                _now(),
                household_account_id,
            ],
        )

    def _resolve_portfolio_account(
        self,
        *,
        conn: Any,
        account_id: str,
        name: str,
        portfolio_account_type: str,
        household_account_id: str,
        cash_balance: Decimal | None,
    ) -> str:
        linked = conn.execute(
            """
            SELECT id
            FROM portfolio_accounts
            WHERE household_account_id = %s
            LIMIT 1
            """,
            [household_account_id],
        ).fetchone()
        if linked is not None:
            conn.execute(
                """
                UPDATE portfolio_accounts
                SET name = %s,
                    account_type = %s,
                    cash_balance = COALESCE(%s, cash_balance),
                    updated_at = %s
                WHERE id = %s
                """,
                [
                    name,
                    portfolio_account_type,
                    float(cash_balance) if cash_balance is not None else None,
                    _now(),
                    str(linked[0]),
                ],
            )
            return str(linked[0])

        portfolio_account_id = f"snaptrade:{account_id}"
        conn.execute(
            """
            INSERT INTO portfolio_accounts (
                id, name, account_type, household_account_id, cash_balance,
                initial_cash, is_spouse, created_at, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, 0, FALSE, %s, %s
            )
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                account_type = EXCLUDED.account_type,
                household_account_id = EXCLUDED.household_account_id,
                cash_balance = COALESCE(EXCLUDED.cash_balance, portfolio_accounts.cash_balance),
                updated_at = EXCLUDED.updated_at
            """,
            [
                portfolio_account_id,
                name,
                portfolio_account_type,
                household_account_id,
                float(cash_balance) if cash_balance is not None else 0.0,
                _now(),
                _now(),
            ],
        )
        return portfolio_account_id

    def _replace_portfolio_positions(
        self,
        *,
        conn: Any,
        account: SnapTradeNormalizedAccount,
        positions: list[SnapTradeNormalizedPosition],
        existing_portfolio_ids: dict[str, str],
        synced_at: datetime,
    ) -> None:
        desired_ids = [
            f"snaptrade:{account.account_id}:{position.position_key}" for position in positions
        ]
        if desired_ids:
            conn.execute(
                """
                DELETE FROM portfolio_positions
                WHERE account_id = %s
                  AND (id LIKE 'snaptrade:%%' OR strategy_id IS NULL)
                  AND id <> ALL(%s)
                """,
                [account.portfolio_account_id, desired_ids],
            )
        else:
            conn.execute(
                """
                DELETE FROM portfolio_positions
                WHERE account_id = %s
                  AND (id LIKE 'snaptrade:%%' OR strategy_id IS NULL)
                """,
                [account.portfolio_account_id],
            )
        for position in positions:
            portfolio_position_id = existing_portfolio_ids.get(
                position.position_key,
                f"snaptrade:{account.account_id}:{position.position_key}",
            )
            conn.execute(
                """
                INSERT INTO portfolio_positions (
                    id, account_id, symbol, shares, cost_basis, position_type,
                    created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (id) DO UPDATE SET
                    account_id = EXCLUDED.account_id,
                    symbol = EXCLUDED.symbol,
                    shares = EXCLUDED.shares,
                    cost_basis = EXCLUDED.cost_basis,
                    position_type = EXCLUDED.position_type,
                    updated_at = EXCLUDED.updated_at
                """,
                [
                    portfolio_position_id,
                    account.portfolio_account_id,
                    position.symbol,
                    float(abs(position.units)),
                    float(self._position_cost_basis_per_share(position)),
                    "short" if position.units < 0 else "long",
                    synced_at,
                    synced_at,
                ],
            )

    def _update_portfolio_account_cash_balance(
        self,
        *,
        conn: Any,
        account: SnapTradeNormalizedAccount,
        positions: list[SnapTradeNormalizedPosition],
        synced_at: datetime,
    ) -> None:
        cash_balance = self._source_cash_balance(account, positions)
        if cash_balance is None:
            return
        conn.execute(
            """
            UPDATE portfolio_accounts
            SET cash_balance = %s,
                updated_at = %s
            WHERE id = %s
            """,
            [float(cash_balance), synced_at, account.portfolio_account_id],
        )
        conn.execute(
            """
            UPDATE snaptrade_accounts
            SET cash_balance = %s,
                last_synced_at = %s
            WHERE account_id = %s
            """,
            [float(cash_balance), synced_at, account.account_id],
        )

    @staticmethod
    def _source_cash_balance(
        account: SnapTradeNormalizedAccount,
        positions: list[SnapTradeNormalizedPosition],
    ) -> Decimal | None:
        if account.balance is None:
            return account.cash_balance

        position_values = [SnapTradeService._position_snapshot_value(position) for position in positions]
        if any(value is None for value in position_values):
            return account.cash_balance

        positions_value = sum((value for value in position_values if value is not None), Decimal("0"))
        residual_cash = SnapTradeService._normalize_cash_residual(account.balance - positions_value)
        if account.cash_balance is None:
            return residual_cash

        cash_overage = abs((positions_value + account.cash_balance) - account.balance)
        if cash_overage <= _CASH_RECONCILIATION_TOLERANCE:
            return account.cash_balance

        logger.warning(
            "snaptrade_cash_balance_reconciled",
            account_id=account.account_id,
            account_name=account.name,
            broker_total=str(account.balance),
            reported_cash=str(account.cash_balance),
            positions_value=str(positions_value),
            residual_cash=str(residual_cash),
        )
        return residual_cash

    @staticmethod
    def _position_snapshot_value(position: SnapTradeNormalizedPosition) -> Decimal | None:
        if position.market_value is not None:
            return position.market_value
        if position.price is not None:
            return position.price * position.units
        return None

    @staticmethod
    def _normalize_cash_residual(value: Decimal) -> Decimal:
        if abs(value) <= _CASH_RECONCILIATION_TOLERANCE:
            return Decimal("0")
        return value

    @staticmethod
    def _position_cost_basis_per_share(position: SnapTradeNormalizedPosition) -> Decimal:
        if position.average_purchase_price is not None:
            return position.average_purchase_price
        if position.cost_basis is not None and position.units:
            return abs(position.cost_basis / position.units)
        if position.price is not None:
            return position.price
        return Decimal("0")

    @staticmethod
    def _account_label(
        institution_name: str | None,
        name: str,
        account_mask: str | None,
    ) -> str:
        label = f"{institution_name} - {name}" if institution_name else name
        if account_mask:
            label = f"{label} *{account_mask}"
        return label

    @staticmethod
    def _account_balance(account: dict[str, object]) -> tuple[Decimal | None, str | None]:
        balance = _dict(account.get("balance"))
        total = _dict(balance.get("total"))
        amount = _decimal(total.get("amount"))
        currency = _currency_code(total.get("currency")) or _currency_code(account.get("currency"))
        return amount, currency

    @staticmethod
    def _cash_balance_from_account(account: dict[str, object]) -> Decimal | None:
        balance = _dict(account.get("balance"))
        for key in ("cash", "cash_balance", "available_cash"):
            parsed = _decimal(balance.get(key))
            if parsed is not None:
                return parsed
        return None

    @staticmethod
    def _account_cash_balance(
        balance_rows: Sequence[object],
        *,
        preferred_currency: str | None = None,
    ) -> tuple[Decimal | None, str | None]:
        candidates: list[tuple[str | None, Decimal]] = []
        for row in balance_rows:
            balance = _dict(row)
            cash = _decimal(balance.get("cash"))
            if cash is None:
                continue
            candidates.append((_currency_code(balance.get("currency")), cash))
        if not candidates:
            return None, preferred_currency

        preferred = preferred_currency.upper() if preferred_currency else None
        for currency, cash in candidates:
            if preferred and currency == preferred:
                return cash, currency
        for currency, cash in candidates:
            if currency == "USD":
                return cash, currency
        currency, cash = candidates[0]
        return cash, currency or preferred

    def _normalize_position(
        self,
        raw_position: dict[str, object],
    ) -> SnapTradeNormalizedPosition | None:
        instrument = _dict(raw_position.get("instrument"))
        legacy_symbol = _dict(raw_position.get("symbol"))
        universal_symbol = _dict(legacy_symbol.get("symbol"))
        symbol = (
            _symbol(instrument.get("symbol"))
            or _symbol(universal_symbol.get("symbol"))
            or _symbol(raw_position.get("symbol"))
        )
        units = _decimal(raw_position.get("units")) or _decimal(
            raw_position.get("fractional_units")
        )
        if symbol is None or units is None or units == 0:
            return None
        security_id = (
            _string(instrument.get("id"))
            or _string(universal_symbol.get("id"))
            or _string(legacy_symbol.get("id"))
        )
        position_key = security_id or symbol
        price = _decimal(raw_position.get("price"))
        average_purchase_price = _decimal(raw_position.get("average_purchase_price"))
        cost_basis = _decimal(raw_position.get("cost_basis"))
        market_value = price * units if price is not None else None
        raw_symbol = _string(instrument.get("raw_symbol")) or _string(
            universal_symbol.get("raw_symbol")
        )
        currency = (
            _currency_code(instrument.get("currency"))
            or _currency_code(universal_symbol.get("currency"))
            or _currency_code(raw_position.get("currency"))
        )
        return SnapTradeNormalizedPosition(
            position_key=position_key,
            symbol=symbol,
            raw_symbol=raw_symbol,
            security_id=security_id,
            security_kind=_string(instrument.get("kind")) or _string(raw_position.get("kind")),
            units=units,
            price=price,
            average_purchase_price=average_purchase_price,
            market_value=market_value,
            cost_basis=cost_basis,
            currency=currency,
            metadata=raw_position,
        )

    def _normalize_order(
        self,
        raw_order: dict[str, object],
    ) -> SnapTradeNormalizedOrder | None:
        brokerage_order_id = _string(raw_order.get("brokerage_order_id")) or _string(
            raw_order.get("id")
        )
        if not brokerage_order_id:
            return None

        universal_symbol = _dict(raw_order.get("universal_symbol"))
        nested_symbol = _dict(raw_order.get("symbol"))
        nested_universal_symbol = _dict(nested_symbol.get("symbol"))
        symbol = (
            _symbol(universal_symbol.get("symbol"))
            or _symbol(nested_universal_symbol.get("symbol"))
            or _symbol(nested_symbol.get("symbol"))
            or _symbol(raw_order.get("symbol"))
        )
        raw_symbol = (
            _string(universal_symbol.get("raw_symbol"))
            or _string(nested_universal_symbol.get("raw_symbol"))
            or _string(nested_symbol.get("raw_symbol"))
        )
        currency = (
            _currency_code(raw_order.get("currency"))
            or _currency_code(universal_symbol.get("currency"))
            or _currency_code(nested_universal_symbol.get("currency"))
        )
        return SnapTradeNormalizedOrder(
            brokerage_order_id=brokerage_order_id,
            status=_string(raw_order.get("status")),
            action=_string(raw_order.get("action")),
            symbol=symbol,
            raw_symbol=raw_symbol,
            filled_quantity=_decimal(raw_order.get("filled_quantity")),
            execution_price=_decimal(raw_order.get("execution_price")),
            order_type=_string(raw_order.get("order_type")),
            time_in_force=_string(raw_order.get("time_in_force")),
            time_placed=_coerce_timestamp(raw_order.get("time_placed")),
            time_updated=_coerce_timestamp(raw_order.get("time_updated")),
            time_executed=_coerce_timestamp(raw_order.get("time_executed")),
            currency=currency,
            metadata=raw_order,
        )

    @staticmethod
    def _activity_symbol(activity: dict[str, object]) -> str | None:
        symbol = _dict(activity.get("symbol"))
        universal_symbol = _dict(symbol.get("symbol"))
        return (
            _symbol(universal_symbol.get("symbol"))
            or _symbol(symbol.get("symbol"))
            or _symbol(activity.get("symbol"))
        )

    def _record_user_error(self, user_id: str, message: str) -> None:
        with self.storage.connection() as conn:
            conn.execute(
                """
                UPDATE snaptrade_users
                SET last_error = %s,
                    updated_at = %s
                WHERE user_id = %s
                """,
                [message, _now(), user_id],
            )
            conn.commit()

    def _record_user_sync(self, user_id: str, *, has_errors: bool) -> None:
        with self.storage.connection() as conn:
            conn.execute(
                """
                UPDATE snaptrade_users
                SET last_successful_sync_at = %s,
                    last_error = CASE WHEN %s THEN last_error ELSE NULL END,
                    updated_at = %s
                WHERE user_id = %s
                """,
                [_now(), has_errors, _now(), user_id],
            )
            conn.commit()


__all__ = [
    "_READ_ONLY_CONNECTION_TYPE",
    "SnapTradeConfigurationError",
    "SnapTradeIntegrationError",
    "SnapTradeReadOnlyClient",
    "SnapTradeService",
    "_connection_portal_kwargs",
    "_redact_account_number",
]
