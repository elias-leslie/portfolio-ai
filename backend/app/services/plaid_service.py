"""Plaid integration for household finance data."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import plaid
from plaid.api import plaid_api
from plaid.model.accounts_balance_get_request import AccountsBalanceGetRequest
from plaid.model.country_code import CountryCode
from plaid.model.institutions_get_by_id_request import InstitutionsGetByIdRequest
from plaid.model.item_get_request import ItemGetRequest
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.item_remove_request import ItemRemoveRequest
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.products import Products
from plaid.model.transactions_sync_request import TransactionsSyncRequest

from app.logging_config import get_logger
from app.services._household_merchants import _canonical_category_from_taxonomy
from app.services.credential_crypto import (
    CredentialCipher,
    SecretDecryptionError,
    SecretKeyUnavailableError,
)
from app.services.household_account_identity import account_identity_candidates
from app.services.household_soft_charge_service import SoftChargeReconciler
from app.services.household_transaction_service import HouseholdTransactionService
from app.services.source_credentials import get_source_credentials, set_source_credential
from app.storage import get_storage

logger = get_logger(__name__)

_PLAID_SOURCE_ID = "plaid"
_DEFAULT_PRODUCTS = ["transactions"]
_DEFAULT_COUNTRY_CODES = ["US"]
_VALID_ENVIRONMENTS = {"sandbox", "production"}
_GENERIC_PLAID_ACCOUNT_NAMES = {"account", "credit card"}
_MASK_IDENTITY_PREFIXES = (
    "institution-mask::",
    "mask::",
    "mask-asset::",
    "evidence|",
)


class PlaidConfigurationError(RuntimeError):
    """Raised when Plaid cannot be used because local configuration is missing."""


class PlaidIntegrationError(RuntimeError):
    """Raised for sanitized Plaid API failures."""

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
class PlaidConfig:
    environment: str
    client_id: str
    secret: str
    products: list[str]
    country_codes: list[str]
    redirect_uri: str | None


def _now() -> datetime:
    return datetime.now(UTC)


def _json(value: object) -> str:
    return json.dumps(value, default=str)


def _as_json_list(value: object, default: list[str]) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return default
        if isinstance(parsed, list):
            return [str(item) for item in parsed if str(item).strip()]
    return default


def _as_json_object(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return {str(key): nested for key, nested in value.items()}
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        if isinstance(parsed, dict):
            return {str(key): nested for key, nested in parsed.items()}
    return {}


def _to_dict(value: Any) -> dict[str, Any]:
    if hasattr(value, "to_dict"):
        converted = value.to_dict()
        return converted if isinstance(converted, dict) else {}
    return value if isinstance(value, dict) else {}


def _parse_date(value: object) -> date | None:
    if isinstance(value, date):
        return value
    if not value:
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _money(value: object) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _plaid_error_payload(exc: plaid.ApiException) -> dict[str, object]:
    try:
        body = json.loads(exc.body or "{}")
    except (TypeError, json.JSONDecodeError):
        body = {}
    return {
        "error_type": body.get("error_type") or "PLAID_API_ERROR",
        "error_code": body.get("error_code") or str(exc.status),
        "error_message": body.get("error_message") or "Plaid request failed.",
        "request_id": body.get("request_id"),
    }


def _metadata_institution_name(metadata: dict[str, object] | None) -> str | None:
    institution = (metadata or {}).get("institution")
    if isinstance(institution, dict):
        name = institution.get("name")
        if name:
            return str(name)
    return None


def _account_kind(account_type: str | None, subtype: str | None) -> tuple[str, str, str]:
    normalized_type = (account_type or "").strip().lower()
    normalized_subtype = (subtype or "").strip().lower().replace(" ", "_")
    if normalized_type == "credit":
        return "credit", "credit_card", "credit_card"
    if normalized_type == "depository":
        return "cash", "bank", normalized_subtype or "depository"
    if normalized_type == "investment":
        return "taxable", "brokerage", normalized_subtype or "investment"
    if normalized_type == "loan":
        return "debt", "loan", normalized_subtype or "loan"
    return "other", "plaid", normalized_subtype or normalized_type or "account"


def _plaid_account_name(account: dict[str, Any]) -> str:
    name = str(account.get("name") or "").strip()
    official_name = str(account.get("official_name") or "").strip()
    if official_name and (not name or name.lower() in _GENERIC_PLAID_ACCOUNT_NAMES):
        return official_name
    return name or official_name or "Plaid account"


def _account_label(
    *,
    institution_name: str | None,
    name: str,
    mask: str | None,
) -> str:
    parts = [part for part in (institution_name, name) if part]
    label = " - ".join(parts) if parts else name
    if mask:
        label = f"{label} *{mask}"
    return label


def _transaction_flow(amount: Decimal, personal_finance_category: dict[str, object]) -> str:
    primary = str(personal_finance_category.get("primary") or "").upper()
    detailed = str(personal_finance_category.get("detailed") or "").upper()
    if amount > 0:
        if primary == "TRANSFER_OUT":
            return "investment" if "INVESTMENT" in detailed else "transfer_out"
        return "expense"
    if primary == "INCOME":
        return "income"
    if primary == "TRANSFER_IN":
        return "transfer_in"
    return "refund"


def _transaction_category(personal_finance_category: dict[str, object]) -> tuple[str, str]:
    raw = (
        personal_finance_category.get("detailed")
        or personal_finance_category.get("primary")
        or "Uncategorized"
    )
    mapped = _canonical_category_from_taxonomy(category=str(raw))
    if mapped is not None:
        return mapped
    return (
        str(raw).replace("_", " ").title(),
        "mixed",
    )


class PlaidService:
    """Create Plaid Link tokens, store item tokens, and sync household data."""

    def __init__(self) -> None:
        self.storage = get_storage()
        self.cipher = CredentialCipher()
        self.transaction_service = HouseholdTransactionService()

    def get_status(self) -> dict[str, object]:
        with self.storage.connection() as conn:
            credential_rows = conn.execute(
                """
                SELECT field, value, updated_at
                FROM source_credentials
                WHERE source_id = %s
                """,
                [_PLAID_SOURCE_ID],
            ).fetchall()
            item_count = conn.execute(
                "SELECT COUNT(*) FROM plaid_items WHERE status = 'active'"
            ).fetchone()
            account_count = conn.execute("SELECT COUNT(*) FROM plaid_accounts").fetchone()
            transaction_count = conn.execute(
                "SELECT COUNT(*) FROM plaid_transactions WHERE removed IS NOT TRUE"
            ).fetchone()
            latest_sync = conn.execute(
                "SELECT MAX(last_successful_sync_at) FROM plaid_items WHERE status = 'active'"
            ).fetchone()
            item_rows = conn.execute(
                """
                SELECT item_id, institution_name, status, last_successful_sync_at, last_error
                FROM plaid_items
                ORDER BY updated_at DESC
                LIMIT 20
                """
            ).fetchall()

        raw_credentials = {str(row[0]): str(row[1]) for row in credential_rows}
        credential_updated_at = [
            row[2]
            for row in credential_rows
            if str(row[0]) in {"client_id", "secret"} and row[1] and isinstance(row[2], datetime)
        ]
        client_id_configured = bool(raw_credentials.get("client_id"))
        secret_configured = bool(raw_credentials.get("secret"))
        configured = client_id_configured and secret_configured
        return {
            "configured": configured,
            "client_id_configured": client_id_configured,
            "secret_configured": secret_configured,
            "configuration_updated_at": max(credential_updated_at).isoformat()
            if credential_updated_at
            else None,
            "encryption_ready": self.cipher.available,
            "environment": raw_credentials.get("environment"),
            "products": _as_json_list(raw_credentials.get("products"), _DEFAULT_PRODUCTS)
            if configured
            else [],
            "country_codes": _as_json_list(
                raw_credentials.get("country_codes"),
                _DEFAULT_COUNTRY_CODES,
            )
            if configured
            else [],
            "redirect_uri": raw_credentials.get("redirect_uri"),
            "item_count": int(item_count[0] or 0) if item_count else 0,
            "account_count": int(account_count[0] or 0) if account_count else 0,
            "transaction_count": int(transaction_count[0] or 0) if transaction_count else 0,
            "last_successful_sync_at": latest_sync[0].isoformat()
            if latest_sync and isinstance(latest_sync[0], datetime)
            else None,
            "items": [
                {
                    "item_id": str(row[0]),
                    "institution_name": str(row[1]) if row[1] else None,
                    "status": str(row[2]),
                    "last_successful_sync_at": row[3].isoformat()
                    if isinstance(row[3], datetime)
                    else None,
                    "last_error": str(row[4]) if row[4] else None,
                }
                for row in item_rows
            ],
        }

    def configure(
        self,
        *,
        client_id: str | None,
        secret: str | None,
        environment: str,
        products: list[str] | None = None,
        country_codes: list[str] | None = None,
        redirect_uri: str | None = None,
    ) -> dict[str, object]:
        environment = environment.strip().lower()
        if environment not in _VALID_ENVIRONMENTS:
            raise PlaidConfigurationError("Plaid environment must be sandbox or production.")
        if not self.cipher.available:
            raise SecretKeyUnavailableError(
                "PORTFOLIO_SECRET_KEY is required for encrypted credentials"
            )
        client_id = client_id.strip() if client_id else ""
        secret = secret.strip() if secret else ""
        existing_credentials = get_source_credentials(self.storage, _PLAID_SOURCE_ID)
        existing_client_id = existing_credentials.get("client_id")
        existing_secret = existing_credentials.get("secret")
        if (not client_id or not secret) and (
            not (client_id or existing_client_id) or not (secret or existing_secret)
        ):
            raise PlaidConfigurationError("Plaid client_id and secret are required.")

        cleaned_products = [
            item.strip() for item in (products or _DEFAULT_PRODUCTS) if item.strip()
        ]
        cleaned_country_codes = [
            item.strip().upper()
            for item in (country_codes or _DEFAULT_COUNTRY_CODES)
            if item.strip()
        ]
        if not cleaned_products:
            cleaned_products = _DEFAULT_PRODUCTS
        if not cleaned_country_codes:
            cleaned_country_codes = _DEFAULT_COUNTRY_CODES

        self._ensure_source_registry()
        if client_id:
            set_source_credential(self.storage, _PLAID_SOURCE_ID, "client_id", client_id)
        if secret:
            set_source_credential(self.storage, _PLAID_SOURCE_ID, "secret", secret)
        set_source_credential(
            self.storage,
            _PLAID_SOURCE_ID,
            "environment",
            environment,
            encrypt=False,
        )
        set_source_credential(
            self.storage,
            _PLAID_SOURCE_ID,
            "products",
            _json(cleaned_products),
            encrypt=False,
        )
        set_source_credential(
            self.storage,
            _PLAID_SOURCE_ID,
            "country_codes",
            _json(cleaned_country_codes),
            encrypt=False,
        )
        set_source_credential(
            self.storage,
            _PLAID_SOURCE_ID,
            "redirect_uri",
            redirect_uri.strip() if redirect_uri else "",
            encrypt=False,
        )
        logger.info("plaid_source_credentials_saved", environment=environment)
        return self.get_status()

    def create_link_token(self) -> dict[str, object]:
        config = self._load_config()
        client = self._client(config)
        request = LinkTokenCreateRequest(
            products=[Products(product) for product in config.products],
            client_name="Portfolio AI",
            country_codes=[CountryCode(code) for code in config.country_codes],
            language="en",
            user=LinkTokenCreateRequestUser(client_user_id="portfolio-ai-household"),
        )
        if config.redirect_uri:
            request["redirect_uri"] = config.redirect_uri
        try:
            return _to_dict(client.link_token_create(request))
        except plaid.ApiException as exc:
            payload = _plaid_error_payload(exc)
            raise PlaidIntegrationError(
                str(payload["error_message"]),
                status_code=502,
                error_payload=payload,
            ) from exc

    def exchange_public_token(
        self,
        *,
        public_token: str,
        metadata: dict[str, object] | None = None,
    ) -> dict[str, object]:
        config = self._load_config()
        client = self._client(config)
        try:
            exchange_response = _to_dict(
                client.item_public_token_exchange(
                    ItemPublicTokenExchangeRequest(public_token=public_token)
                )
            )
        except plaid.ApiException as exc:
            payload = _plaid_error_payload(exc)
            raise PlaidIntegrationError(
                str(payload["error_message"]),
                status_code=502,
                error_payload=payload,
            ) from exc

        access_token = str(exchange_response.get("access_token") or "")
        item_id = str(exchange_response.get("item_id") or "")
        if not access_token or not item_id:
            raise PlaidIntegrationError("Plaid did not return an item token.")

        item_info = self._item_info(client, access_token, config.country_codes)
        institution_name = item_info.get("institution_name") or _metadata_institution_name(metadata)
        now = _now()
        with self.storage.connection() as conn:
            conn.execute(
                """
                INSERT INTO plaid_items (
                    id, item_id, access_token_ciphertext, environment, institution_id,
                    institution_name, available_products, billed_products, consented_products,
                    metadata, status, created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb,
                    %s::jsonb, 'active', %s, %s
                )
                ON CONFLICT (item_id) DO UPDATE SET
                    access_token_ciphertext = EXCLUDED.access_token_ciphertext,
                    environment = EXCLUDED.environment,
                    institution_id = EXCLUDED.institution_id,
                    institution_name = EXCLUDED.institution_name,
                    available_products = EXCLUDED.available_products,
                    billed_products = EXCLUDED.billed_products,
                    consented_products = EXCLUDED.consented_products,
                    metadata = plaid_items.metadata || EXCLUDED.metadata,
                    status = 'active',
                    last_error = NULL,
                    updated_at = EXCLUDED.updated_at
                """,
                [
                    str(uuid.uuid4()),
                    item_id,
                    self.cipher.encrypt(access_token),
                    config.environment,
                    item_info.get("institution_id"),
                    institution_name,
                    _json(item_info.get("available_products", [])),
                    _json(item_info.get("billed_products", [])),
                    _json(item_info.get("consented_products", [])),
                    _json({"link_metadata": metadata or {}}),
                    now,
                    now,
                ],
            )
            conn.commit()
        logger.info(
            "plaid_item_linked",
            item_id=item_id,
            institution_id=item_info.get("institution_id"),
        )
        return {
            "item_id": item_id,
            "institution_name": institution_name,
            "sync": self.sync_items(item_id=item_id),
        }

    def sync_items(self, *, item_id: str | None = None) -> dict[str, object]:
        items = self._load_items(item_id=item_id)
        totals: dict[str, object] = {
            "item_count": 0,
            "account_count": 0,
            "transaction_added_count": 0,
            "transaction_modified_count": 0,
            "transaction_removed_count": 0,
            "errors": [],
        }
        config = self._load_config()
        client = self._client(config)

        for item in items:
            totals["item_count"] = int(totals["item_count"]) + 1
            try:
                item_result = self._sync_single_item(client=client, item=item)
            except plaid.ApiException as exc:
                payload = _plaid_error_payload(exc)
                self._record_item_error(item["item_id"], str(payload["error_message"]))
                cast_errors = totals["errors"]
                if isinstance(cast_errors, list):
                    cast_errors.append({"item_id": item["item_id"], **payload})
                continue
            except (SecretDecryptionError, SecretKeyUnavailableError) as exc:
                self._record_item_error(item["item_id"], str(exc))
                cast_errors = totals["errors"]
                if isinstance(cast_errors, list):
                    cast_errors.append({"item_id": item["item_id"], "error_message": str(exc)})
                continue

            totals["account_count"] = int(totals["account_count"]) + int(
                item_result["account_count"]
            )
            totals["transaction_added_count"] = int(totals["transaction_added_count"]) + int(
                item_result["transaction_added_count"]
            )
            totals["transaction_modified_count"] = int(totals["transaction_modified_count"]) + int(
                item_result["transaction_modified_count"]
            )
            totals["transaction_removed_count"] = int(totals["transaction_removed_count"]) + int(
                item_result["transaction_removed_count"]
            )

        return totals

    def remove_item(self, *, item_id: str) -> dict[str, bool]:
        config = self._load_config()
        client = self._client(config)
        item = self._load_items(item_id=item_id)
        if not item:
            return {"ok": False}
        access_token = self.cipher.decrypt(str(item[0]["access_token_ciphertext"]))
        try:
            client.item_remove(ItemRemoveRequest(access_token=access_token))
        except plaid.ApiException as exc:
            payload = _plaid_error_payload(exc)
            raise PlaidIntegrationError(
                str(payload["error_message"]),
                status_code=502,
                error_payload=payload,
            ) from exc
        with self.storage.connection() as conn:
            conn.execute(
                """
                UPDATE plaid_items
                SET status = 'removed',
                    access_token_ciphertext = '',
                    updated_at = %s
                WHERE item_id = %s
                """,
                [_now(), item_id],
            )
            conn.commit()
        logger.info("plaid_item_removed", item_id=item_id)
        return {"ok": True}

    def _ensure_source_registry(self) -> None:
        with self.storage.connection() as conn:
            conn.execute(
                """
                INSERT INTO source_registry (
                    source_id, display_name, priority, enabled, definition, created_at, updated_at
                ) VALUES (
                    %s, 'Plaid', 50, TRUE,
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
                    _PLAID_SOURCE_ID,
                    _json(
                        {
                            "category": "household_finance",
                            "credential_store": "source_credentials",
                        }
                    ),
                ],
            )
            conn.commit()

    def _load_config(self) -> PlaidConfig:
        if not self.cipher.available:
            raise SecretKeyUnavailableError(
                "PORTFOLIO_SECRET_KEY is required for encrypted credentials"
            )
        credentials = get_source_credentials(self.storage, _PLAID_SOURCE_ID)
        client_id = credentials.get("client_id")
        secret = credentials.get("secret")
        if not client_id or not secret:
            raise PlaidConfigurationError("Plaid credentials are not configured.")
        environment = (credentials.get("environment") or "sandbox").strip().lower()
        if environment not in _VALID_ENVIRONMENTS:
            raise PlaidConfigurationError("Plaid environment must be sandbox or production.")
        return PlaidConfig(
            environment=environment,
            client_id=client_id,
            secret=secret,
            products=_as_json_list(credentials.get("products"), _DEFAULT_PRODUCTS),
            country_codes=_as_json_list(credentials.get("country_codes"), _DEFAULT_COUNTRY_CODES),
            redirect_uri=credentials.get("redirect_uri"),
        )

    def _load_items(self, *, item_id: str | None = None) -> list[dict[str, object]]:
        params: list[object] = ["active"]
        where = "WHERE status = %s"
        if item_id:
            where += " AND item_id = %s"
            params.append(item_id)
        with self.storage.connection() as conn:
            rows = conn.execute(
                f"""
                SELECT item_id, access_token_ciphertext, environment, institution_id,
                       institution_name, transactions_cursor
                FROM plaid_items
                {where}
                ORDER BY updated_at DESC
                """,
                params,
            ).fetchall()
        return [
            {
                "item_id": str(row[0]),
                "access_token_ciphertext": str(row[1]),
                "environment": str(row[2]),
                "institution_id": str(row[3]) if row[3] else None,
                "institution_name": str(row[4]) if row[4] else None,
                "transactions_cursor": str(row[5]) if row[5] else "",
            }
            for row in rows
        ]

    @staticmethod
    def _client(config: PlaidConfig) -> plaid_api.PlaidApi:
        host = plaid.Environment.Sandbox
        if config.environment == "production":
            host = plaid.Environment.Production
        configuration = plaid.Configuration(
            host=host,
            api_key={
                "clientId": config.client_id,
                "secret": config.secret,
                "plaidVersion": "2020-09-14",
            },
        )
        return plaid_api.PlaidApi(plaid.ApiClient(configuration))

    def _item_info(
        self,
        client: plaid_api.PlaidApi,
        access_token: str,
        country_codes: list[str],
    ) -> dict[str, object]:
        item_response = _to_dict(client.item_get(ItemGetRequest(access_token=access_token)))
        item = item_response.get("item") if isinstance(item_response.get("item"), dict) else {}
        institution_id = item.get("institution_id") if isinstance(item, dict) else None
        institution_name = None
        if institution_id:
            try:
                institution_response = _to_dict(
                    client.institutions_get_by_id(
                        InstitutionsGetByIdRequest(
                            institution_id=str(institution_id),
                            country_codes=[CountryCode(code) for code in country_codes],
                        )
                    )
                )
                institution = institution_response.get("institution")
                if isinstance(institution, dict) and institution.get("name"):
                    institution_name = str(institution["name"])
            except plaid.ApiException:
                institution_name = None
        return {
            "institution_id": str(institution_id) if institution_id else None,
            "institution_name": institution_name,
            "available_products": item.get("available_products", [])
            if isinstance(item, dict)
            else [],
            "billed_products": item.get("billed_products", []) if isinstance(item, dict) else [],
            "consented_products": item.get("consented_products", [])
            if isinstance(item, dict)
            else [],
        }

    def _sync_single_item(
        self,
        *,
        client: plaid_api.PlaidApi,
        item: dict[str, object],
    ) -> dict[str, int]:
        item_id = str(item["item_id"])
        access_token = self.cipher.decrypt(str(item["access_token_ciphertext"]))
        accounts_response = _to_dict(
            client.accounts_balance_get(AccountsBalanceGetRequest(access_token=access_token))
        )
        accounts = (
            accounts_response.get("accounts")
            if isinstance(accounts_response.get("accounts"), list)
            else []
        )
        document_id = self._ensure_sync_document(item=item)
        account_count = self._upsert_accounts(
            item=item,
            document_id=document_id,
            accounts=accounts,
        )
        transaction_counts, next_cursor = self._sync_transactions(
            client=client,
            item=item,
            document_id=document_id,
            access_token=access_token,
        )
        with self.storage.connection() as conn:
            conn.execute(
                """
                UPDATE plaid_items
                SET transactions_cursor = COALESCE(%s, transactions_cursor),
                    last_successful_sync_at = %s,
                    last_error = NULL,
                    updated_at = %s
                WHERE item_id = %s
                """,
                [next_cursor, _now(), _now(), item_id],
            )
            conn.commit()
        return {"account_count": account_count, **transaction_counts}

    def _ensure_sync_document(self, *, item: dict[str, object]) -> str:
        item_id = str(item["item_id"])
        institution_name = str(item.get("institution_name") or "Plaid")
        now = _now()
        metadata = {
            "plaid_item_id": item_id,
            "plaid_institution_id": item.get("institution_id"),
            "source": "plaid",
        }
        with self.storage.connection() as conn:
            existing = conn.execute(
                """
                SELECT id
                FROM household_documents
                WHERE source_type = 'plaid'
                  AND document_type = 'api_sync'
                  AND metadata->>'plaid_item_id' = %s
                ORDER BY uploaded_at DESC
                LIMIT 1
                """,
                [item_id],
            ).fetchone()
            if existing is not None:
                document_id = str(existing[0])
                conn.execute(
                    """
                    UPDATE household_documents
                    SET status = 'parsed',
                        review_status = 'complete',
                        parsed_at = %s,
                        metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb
                    WHERE id = %s
                    """,
                    [now, _json(metadata), document_id],
                )
            else:
                document_id = str(uuid.uuid4())
                conn.execute(
                    """
                    INSERT INTO household_documents (
                        id, filename, stored_path, source_type, document_type, status,
                        account_label, content_type, file_size_bytes,
                        classification_confidence, uploaded_at, parsed_at, metadata,
                        review_status, review_summary, review_confidence
                    ) VALUES (
                        %s, %s, %s, 'plaid', 'api_sync', 'parsed',
                        %s, 'application/json', 0,
                        1.0, %s, %s, %s::jsonb,
                        'complete', %s, 1.0
                    )
                    """,
                    [
                        document_id,
                        f"Plaid - {institution_name}",
                        f"plaid://items/{item_id}",
                        institution_name,
                        now,
                        now,
                        _json(metadata),
                        f"Plaid account sync for {institution_name}.",
                    ],
                )
            conn.commit()
        return document_id

    def _upsert_accounts(
        self,
        *,
        item: dict[str, object],
        document_id: str,
        accounts: list[object],
    ) -> int:
        item_id = str(item["item_id"])
        institution_name = str(item.get("institution_name") or "Plaid")
        synced_at = _now()
        count = 0
        with self.storage.connection() as conn:
            conn.execute(
                """
                DELETE FROM household_evidence_accounts
                WHERE document_id = %s
                  AND metadata->>'plaid_item_id' = %s
                """,
                [document_id, item_id],
            )
            for raw_account in accounts:
                account = _to_dict(raw_account)
                account_id = str(account.get("account_id") or "")
                name = _plaid_account_name(account)
                if not account_id:
                    continue
                balances = _as_json_object(account.get("balances"))
                current_balance = _money(balances.get("current"))
                available_balance = _money(balances.get("available"))
                account_type = str(account.get("type") or "")
                subtype = str(account.get("subtype") or "")
                asset_group, source_type, normalized_account_type = _account_kind(
                    account_type,
                    subtype,
                )
                mask = str(account.get("mask")) if account.get("mask") else None
                label = _account_label(
                    institution_name=institution_name,
                    name=name,
                    mask=mask,
                )
                household_account_id = self._upsert_household_account(
                    conn=conn,
                    account_id=account_id,
                    label=label,
                    asset_group=asset_group,
                    source_type=source_type,
                    account_type=normalized_account_type,
                    institution_name=institution_name,
                    mask=mask,
                )
                conn.execute(
                    """
                    INSERT INTO plaid_accounts (
                        id, item_id, account_id, household_account_id, name, official_name,
                        mask, type, subtype, verification_status, current_balance,
                        available_balance, iso_currency_code, unofficial_currency_code,
                        metadata, last_synced_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s::jsonb, %s
                    )
                    ON CONFLICT (account_id) DO UPDATE SET
                        household_account_id = EXCLUDED.household_account_id,
                        name = EXCLUDED.name,
                        official_name = EXCLUDED.official_name,
                        mask = EXCLUDED.mask,
                        type = EXCLUDED.type,
                        subtype = EXCLUDED.subtype,
                        verification_status = EXCLUDED.verification_status,
                        current_balance = EXCLUDED.current_balance,
                        available_balance = EXCLUDED.available_balance,
                        iso_currency_code = EXCLUDED.iso_currency_code,
                        unofficial_currency_code = EXCLUDED.unofficial_currency_code,
                        metadata = EXCLUDED.metadata,
                        last_synced_at = EXCLUDED.last_synced_at
                    """,
                    [
                        str(uuid.uuid4()),
                        item_id,
                        account_id,
                        household_account_id,
                        name,
                        account.get("official_name"),
                        mask,
                        account_type,
                        subtype,
                        account.get("verification_status"),
                        current_balance,
                        available_balance,
                        balances.get("iso_currency_code"),
                        balances.get("unofficial_currency_code"),
                        _json(account),
                        synced_at,
                    ],
                )
                conn.execute(
                    """
                    INSERT INTO household_evidence_accounts (
                        id, document_id, household_account_id, source_type, asset_group,
                        account_type, institution_name, account_name, account_mask,
                        currency, balance, cash_balance, as_of_date, confidence,
                        metadata, created_at, updated_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        1.0, %s::jsonb, %s, %s
                    )
                    """,
                    [
                        str(uuid.uuid4()),
                        document_id,
                        household_account_id,
                        source_type,
                        asset_group,
                        normalized_account_type,
                        institution_name,
                        name,
                        mask,
                        balances.get("iso_currency_code"),
                        current_balance,
                        available_balance,
                        synced_at,
                        _json({"plaid_item_id": item_id, "plaid_account_id": account_id}),
                        synced_at,
                        synced_at,
                    ],
                )
                count += 1
            conn.commit()
        return count

    def _upsert_household_account(
        self,
        *,
        conn: Any,
        account_id: str,
        label: str,
        asset_group: str,
        source_type: str,
        account_type: str,
        institution_name: str,
        mask: str | None,
    ) -> str:
        identity_key = f"plaid_account:{account_id}"
        mask_identity_keys = [
            key
            for key in account_identity_candidates(
                source_type=source_type,
                asset_group=asset_group,
                account_type=account_type,
                institution_name=institution_name,
                account_name=label,
                owner_name=None,
                account_mask=mask,
            )
            if key.startswith(_MASK_IDENTITY_PREFIXES)
        ]
        household_account_id = self._match_household_account_identity(
            conn=conn,
            identity_keys=mask_identity_keys,
        ) or self._match_household_account_identity(
            conn=conn,
            identity_keys=[identity_key],
        )

        if household_account_id:
            conn.execute(
                """
                UPDATE household_accounts
                SET canonical_label = CASE
                        WHEN canonical_label IS NULL
                          OR lower(canonical_label) IN ('account', 'credit card')
                        THEN %s
                        ELSE canonical_label
                    END,
                    asset_group = %s,
                    account_type = %s,
                    source_type = %s,
                    institution_name = %s,
                    account_mask = COALESCE(%s, account_mask),
                    metadata = metadata || %s::jsonb,
                    updated_at = %s
                WHERE id = %s
                """,
                [
                    label,
                    asset_group,
                    account_type,
                    source_type,
                    institution_name,
                    mask,
                    _json({"plaid_account_id": account_id}),
                    _now(),
                    household_account_id,
                ],
            )
        else:
            row = conn.execute(
                """
                INSERT INTO household_accounts (
                    id, primary_identity_key, canonical_label, asset_group, account_type,
                    source_type, institution_name, account_mask, metadata, created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s
                )
                ON CONFLICT (primary_identity_key) WHERE primary_identity_key IS NOT NULL DO UPDATE SET
                    canonical_label = EXCLUDED.canonical_label,
                    asset_group = EXCLUDED.asset_group,
                    account_type = EXCLUDED.account_type,
                    source_type = EXCLUDED.source_type,
                    institution_name = EXCLUDED.institution_name,
                    account_mask = EXCLUDED.account_mask,
                    metadata = household_accounts.metadata || EXCLUDED.metadata,
                    updated_at = EXCLUDED.updated_at
                RETURNING id
                """,
                [
                    str(uuid.uuid4()),
                    identity_key,
                    label,
                    asset_group,
                    account_type,
                    source_type,
                    institution_name,
                    mask,
                    _json({"plaid_account_id": account_id}),
                    _now(),
                    _now(),
                ],
            ).fetchone()
            household_account_id = str(row[0])

        self._upsert_household_account_identity(
            conn=conn,
            household_account_id=household_account_id,
            identity_key=identity_key,
            identity_kind="plaid_account",
            is_primary=True,
            metadata={"source": "plaid"},
        )
        for mask_identity_key in mask_identity_keys:
            self._upsert_household_account_identity(
                conn=conn,
                household_account_id=household_account_id,
                identity_key=mask_identity_key,
                identity_kind="plaid_mask",
                is_primary=False,
                metadata={"source": "plaid"},
            )
        return household_account_id

    @staticmethod
    def _match_household_account_identity(
        *,
        conn: Any,
        identity_keys: list[str],
    ) -> str | None:
        if not identity_keys:
            return None
        rows = conn.execute(
            """
            SELECT identity_key, household_account_id
            FROM household_account_identities
            WHERE identity_key = ANY(%s)
            """,
            [identity_keys],
        ).fetchall()
        by_key = {str(row[0]): str(row[1]) for row in rows if row[0] and row[1]}
        for identity_key in identity_keys:
            if identity_key in by_key:
                return by_key[identity_key]
        return None

    @staticmethod
    def _upsert_household_account_identity(
        *,
        conn: Any,
        household_account_id: str,
        identity_key: str,
        identity_kind: str,
        is_primary: bool,
        metadata: dict[str, object],
    ) -> None:
        conn.execute(
            """
            INSERT INTO household_account_identities (
                id, household_account_id, identity_key, identity_kind, is_primary,
                confidence, metadata, created_at, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, 1.0, %s::jsonb, %s, %s
            )
            ON CONFLICT (identity_key) DO UPDATE SET
                household_account_id = EXCLUDED.household_account_id,
                is_primary = EXCLUDED.is_primary,
                confidence = 1.0,
                metadata = household_account_identities.metadata || EXCLUDED.metadata,
                updated_at = EXCLUDED.updated_at
            """,
            [
                str(uuid.uuid4()),
                household_account_id,
                identity_key,
                identity_kind,
                is_primary,
                _json(metadata),
                _now(),
                _now(),
            ],
        )

    def _sync_transactions(
        self,
        *,
        client: plaid_api.PlaidApi,
        item: dict[str, object],
        document_id: str,
        access_token: str,
    ) -> tuple[dict[str, int], str | None]:
        cursor = str(item.get("transactions_cursor") or "")
        added: list[dict[str, object]] = []
        modified: list[dict[str, object]] = []
        removed: list[dict[str, object]] = []
        has_more = True
        next_cursor: str | None = cursor
        while has_more:
            response = _to_dict(
                client.transactions_sync(
                    TransactionsSyncRequest(access_token=access_token, cursor=next_cursor or "")
                )
            )
            added.extend(response.get("added") if isinstance(response.get("added"), list) else [])
            modified.extend(
                response.get("modified") if isinstance(response.get("modified"), list) else []
            )
            removed.extend(
                response.get("removed") if isinstance(response.get("removed"), list) else []
            )
            has_more = bool(response.get("has_more"))
            next_cursor = str(response.get("next_cursor") or next_cursor or "")
            if not next_cursor:
                break

        with self.storage.connection() as conn:
            for transaction in added:
                self._upsert_transaction(
                    conn=conn,
                    item=item,
                    document_id=document_id,
                    transaction=transaction,
                    removed=False,
                )
            for transaction in modified:
                self._upsert_transaction(
                    conn=conn,
                    item=item,
                    document_id=document_id,
                    transaction=transaction,
                    removed=False,
                )
            for transaction in removed:
                self._upsert_transaction(
                    conn=conn,
                    item=item,
                    document_id=document_id,
                    transaction=transaction,
                    removed=True,
                )
            conn.commit()
        return (
            {
                "transaction_added_count": len(added),
                "transaction_modified_count": len(modified),
                "transaction_removed_count": len(removed),
            },
            next_cursor or None,
        )

    def _upsert_transaction(
        self,
        *,
        conn: Any,
        item: dict[str, object],
        document_id: str,
        transaction: dict[str, object],
        removed: bool,
    ) -> None:
        transaction_id = str(transaction.get("transaction_id") or "")
        if not transaction_id:
            return
        item_id = str(item["item_id"])
        if removed:
            row_hash = hashlib.sha256(f"plaid|{transaction_id}".encode()).hexdigest()
            conn.execute(
                """
                UPDATE household_transactions
                SET removed = TRUE,
                    updated_at = %s
                WHERE row_hash = %s
                """,
                [_now(), row_hash],
            )
            conn.execute(
                """
                UPDATE plaid_transactions
                SET removed = TRUE,
                    metadata = metadata || %s::jsonb,
                    updated_at = %s
                WHERE transaction_id = %s
                """,
                [
                    _json(transaction),
                    _now(),
                    transaction_id,
                ],
            )
            return

        transaction_date = _parse_date(transaction.get("date"))
        if transaction_date is None:
            return
        amount = _money(transaction.get("amount"))
        if amount is None:
            return
        account_id = str(transaction.get("account_id") or "")
        personal_finance_category = _as_json_object(transaction.get("personal_finance_category"))
        category, essentiality = _transaction_category(personal_finance_category)
        flow_type = _transaction_flow(amount, personal_finance_category)
        merchant = str(
            transaction.get("merchant_name")
            or transaction.get("name")
            or transaction.get("original_description")
            or "Plaid transaction"
        )
        household_amount = abs(amount)
        account_row = conn.execute(
            """
            SELECT household_account_id, name
            FROM plaid_accounts
            WHERE account_id = %s
            """,
            [account_id],
        ).fetchone()
        household_account_id = str(account_row[0]) if account_row and account_row[0] else None
        account_label = str(account_row[1]) if account_row and account_row[1] else None
        merchant_id, canonical_name, category, essentiality, has_manual_rule, rule_id = (
            self.transaction_service._resolve_merchant(
                conn=conn,
                raw_merchant=merchant,
                category=category,
                essentiality=essentiality,
            )
        )
        categorization_source = "merchant_rule" if has_manual_rule else "plaid"
        row_hash = hashlib.sha256(f"plaid|{transaction_id}".encode()).hexdigest()
        authorized_date = _parse_date(transaction.get("authorized_date"))
        now = _now()
        conn.execute(
            """
            INSERT INTO plaid_transactions (
                id, item_id, account_id, transaction_id, name, merchant_name, amount,
                iso_currency_code, unofficial_currency_code, transaction_date,
                authorized_date, pending, payment_channel, category,
                personal_finance_category, removed, metadata, created_at, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s::jsonb, %s::jsonb, FALSE, %s::jsonb, %s, %s
            )
            ON CONFLICT (transaction_id) DO UPDATE SET
                account_id = EXCLUDED.account_id,
                name = EXCLUDED.name,
                merchant_name = EXCLUDED.merchant_name,
                amount = EXCLUDED.amount,
                iso_currency_code = EXCLUDED.iso_currency_code,
                unofficial_currency_code = EXCLUDED.unofficial_currency_code,
                transaction_date = EXCLUDED.transaction_date,
                authorized_date = EXCLUDED.authorized_date,
                pending = EXCLUDED.pending,
                payment_channel = EXCLUDED.payment_channel,
                category = EXCLUDED.category,
                personal_finance_category = EXCLUDED.personal_finance_category,
                removed = FALSE,
                metadata = EXCLUDED.metadata,
                updated_at = EXCLUDED.updated_at
            """,
            [
                str(uuid.uuid4()),
                item_id,
                account_id,
                transaction_id,
                str(transaction.get("name") or merchant),
                transaction.get("merchant_name"),
                amount,
                transaction.get("iso_currency_code"),
                transaction.get("unofficial_currency_code"),
                transaction_date,
                authorized_date,
                bool(transaction.get("pending")),
                transaction.get("payment_channel"),
                _json(transaction.get("category") or []),
                _json(personal_finance_category),
                _json(transaction),
                now,
                now,
            ],
        )
        conn.execute(
            """
            INSERT INTO household_transactions (
                id, document_id, household_account_id, merchant_id, row_hash,
                transaction_date, posted_date, description, raw_merchant, account_label,
                amount, currency, flow_type, category, essentiality, confidence,
                metadata, source_system, external_transaction_id, original_category,
                categorization_source, categorization_version, category_updated_at,
                category_updated_by, transaction_rule_id, pending, removed, created_at,
                updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                1.0, %s::jsonb, 'plaid', %s, %s, %s, %s, %s, %s, %s, %s,
                FALSE, %s, %s
            )
            ON CONFLICT (row_hash) DO UPDATE SET
                document_id = EXCLUDED.document_id,
                household_account_id = EXCLUDED.household_account_id,
                merchant_id = EXCLUDED.merchant_id,
                transaction_date = EXCLUDED.transaction_date,
                posted_date = EXCLUDED.posted_date,
                description = EXCLUDED.description,
                raw_merchant = EXCLUDED.raw_merchant,
                account_label = EXCLUDED.account_label,
                amount = EXCLUDED.amount,
                currency = EXCLUDED.currency,
                flow_type = EXCLUDED.flow_type,
                category = CASE
                    WHEN household_transactions.categorization_source IN ('manual', 'manual_rule', 'merchant_rule')
                        THEN household_transactions.category
                    ELSE EXCLUDED.category
                END,
                essentiality = CASE
                    WHEN household_transactions.categorization_source IN ('manual', 'manual_rule', 'merchant_rule')
                        THEN household_transactions.essentiality
                    ELSE EXCLUDED.essentiality
                END,
                confidence = EXCLUDED.confidence,
                metadata = household_transactions.metadata || EXCLUDED.metadata,
                source_system = 'plaid',
                external_transaction_id = EXCLUDED.external_transaction_id,
                original_category = COALESCE(household_transactions.original_category, EXCLUDED.original_category),
                categorization_source = CASE
                    WHEN household_transactions.categorization_source IN ('manual', 'manual_rule', 'merchant_rule')
                        THEN household_transactions.categorization_source
                    ELSE EXCLUDED.categorization_source
                END,
                categorization_version = EXCLUDED.categorization_version,
                category_updated_at = CASE
                    WHEN household_transactions.categorization_source IN ('manual', 'manual_rule', 'merchant_rule')
                        THEN household_transactions.category_updated_at
                    ELSE EXCLUDED.category_updated_at
                END,
                category_updated_by = CASE
                    WHEN household_transactions.categorization_source IN ('manual', 'manual_rule', 'merchant_rule')
                        THEN household_transactions.category_updated_by
                    ELSE EXCLUDED.category_updated_by
                END,
                transaction_rule_id = CASE
                    WHEN household_transactions.categorization_source IN ('manual', 'manual_rule', 'merchant_rule')
                        THEN household_transactions.transaction_rule_id
                    ELSE EXCLUDED.transaction_rule_id
                END,
                pending = EXCLUDED.pending,
                removed = FALSE,
                updated_at = EXCLUDED.updated_at
            """,
            [
                str(uuid.uuid4()),
                document_id,
                household_account_id,
                merchant_id,
                row_hash,
                datetime.combine(transaction_date, datetime.min.time(), tzinfo=UTC),
                datetime.combine(authorized_date, datetime.min.time(), tzinfo=UTC)
                if authorized_date
                else None,
                str(transaction.get("name") or merchant),
                canonical_name,
                account_label,
                household_amount,
                transaction.get("iso_currency_code") or "USD",
                flow_type,
                category,
                essentiality,
                _json({"plaid_transaction_id": transaction_id, "plaid_item_id": item_id}),
                transaction_id,
                str(personal_finance_category.get("detailed") or personal_finance_category.get("primary") or ""),
                categorization_source,
                "2026-05-canonical",
                now,
                categorization_source,
                rule_id,
                bool(transaction.get("pending")),
                now,
                now,
            ],
        )
        # Reconcile any pending soft charge against this hard row, in the same
        # DB transaction, so the soft mirror void is atomic with the hard upsert
        # (plan §5 — no double counting).
        SoftChargeReconciler.try_match(
            conn=conn,
            hard_row_hash=row_hash,
            household_account_id=household_account_id,
            amount=household_amount,
            occurred_on=transaction_date,
            merchant=canonical_name,
            description=str(transaction.get("name") or merchant),
        )

    def _record_item_error(self, item_id: str, message: str) -> None:
        with self.storage.connection() as conn:
            conn.execute(
                """
                UPDATE plaid_items
                SET last_error = %s,
                    updated_at = %s
                WHERE item_id = %s
                """,
                [message, _now(), item_id],
            )
            conn.commit()
