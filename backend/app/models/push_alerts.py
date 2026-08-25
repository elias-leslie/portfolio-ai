"""Shapes for the household push channel (plan §7 3.6, D11).

A subscription is a device that has said yes, not a person who has: the browser
mints an endpoint, the household says whose phone it is, and every later alert
routes on that pairing. The private VAPID key is a server secret and appears in
none of these models — only the public key, which the browser cannot subscribe
without.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

__all__ = [
    "PushConfig",
    "PushDelivery",
    "PushRecipient",
    "PushSubscriptionInput",
    "PushSubscriptionList",
    "PushSubscriptionView",
    "PushTestRequest",
]


class PushConfig(BaseModel):
    """What a browser needs before it can subscribe."""

    # False when no VAPID key is configured: the UI says so instead of offering
    # a button that can only fail.
    enabled: bool = False
    public_key: str = ""


class PushSubscriptionKeys(BaseModel):
    """The browser's own public encryption material, from ``PushSubscription``.

    The browser calls these ``p256dh`` and ``auth``. They are spelled out here
    because the frontend client rewrites camelCase to snake_case on every
    request body, and it renders ``p256dh`` as ``p_256_dh`` — a field the
    browser never sends and this model would never bind. Explicit names survive
    the round trip and say what each value is; the columns keep the spec names.
    """

    encryption_key: str  # p256dh — the device's public key
    auth_secret: str  # auth — the shared secret for the payload envelope


class PushSubscriptionInput(BaseModel):
    """A registration from one device."""

    endpoint: str
    keys: PushSubscriptionKeys
    household_member_id: str | None = None
    device_label: str | None = None
    user_agent: str | None = None


class PushSubscriptionView(BaseModel):
    """A registered device, as the settings card lists it.

    The endpoint is a bearer capability — anyone holding it can push to the
    device — so it is never returned. ``id`` addresses the row instead.
    """

    id: str
    household_member_id: str | None = None
    member_name: str | None = None
    device_label: str | None = None
    created_at: str | None = None
    last_success_at: str | None = None
    last_failure_at: str | None = None
    last_error: str | None = None


class PushRecipient(BaseModel):
    """An adult who can receive budget alerts.

    The girls are capture-only (D15) and are not offered here: a phone that
    cannot act on a cap being hit should not be interrupted by one.
    """

    id: str
    name: str


class PushSubscriptionList(BaseModel):
    enabled: bool = False
    public_key: str = ""
    recipients: list[PushRecipient] = Field(default_factory=list)
    subscriptions: list[PushSubscriptionView] = Field(default_factory=list)


class PushTestRequest(BaseModel):
    """Send a real push to prove the round trip, optionally to one device."""

    subscription_id: str | None = None


class PushDelivery(BaseModel):
    """What one send actually did.

    ``expired`` counts devices the push service reported gone (404/410); those
    rows are deleted, because a subscription the browser has replaced can never
    be delivered to again and keeping it only re-fails forever.
    """

    delivered: int = 0
    failed: int = 0
    expired: int = 0
