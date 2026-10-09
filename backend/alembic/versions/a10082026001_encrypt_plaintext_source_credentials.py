"""Re-encrypt legacy plaintext secrets in source_credentials.

Idempotent data migration: only secret fields without the ``enc:v1:`` prefix
are rewritten, and each UPDATE is guarded by the old value. Non-secret
provider settings (environment, products, ...) stay plaintext by design.

When PORTFOLIO_SECRET_KEY is not configured the migration logs and leaves the
rows untouched (reads keep working and log a warning). Downgrade is a no-op,
so once the key is available the migration can be re-applied by stepping back
to ``a09232026002`` and upgrading again.
"""

import logging

import sqlalchemy as sa
from alembic import op

from app.services.credential_crypto import CredentialCipher
from app.services.source_credentials import plan_plaintext_reencryption

revision = "a10082026001"
down_revision = "a09232026002"
branch_labels = None
depends_on = None

_log = logging.getLogger("alembic.runtime.migration")


def upgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("source_credentials"):
        return
    cipher = CredentialCipher()
    rows = bind.execute(
        sa.text(
            "SELECT source_id, field, value FROM source_credentials "
            "WHERE value IS NOT NULL AND value NOT LIKE :encrypted_prefix"
        ),
        {"encrypted_prefix": "enc:v1:%"},
    ).fetchall()
    if not rows:
        return
    if not cipher.available:
        _log.warning(
            "PORTFOLIO_SECRET_KEY unavailable; leaving %d plaintext source_credentials rows "
            "unencrypted",
            len(rows),
        )
        return
    originals = {(str(r[0]), str(r[1])): str(r[2]) for r in rows}
    updates = plan_plaintext_reencryption(
        [(source_id, field, value) for (source_id, field), value in originals.items()],
        cipher,
    )
    for source_id, field, encrypted in updates:
        bind.execute(
            sa.text(
                "UPDATE source_credentials SET value = :encrypted, updated_at = CURRENT_TIMESTAMP "
                "WHERE source_id = :source_id AND field = :field AND value = :original"
            ),
            {
                "encrypted": encrypted,
                "source_id": source_id,
                "field": field,
                "original": originals[(source_id, field)],
            },
        )
    _log.info("Encrypted %d legacy plaintext source_credentials rows", len(updates))


def downgrade() -> None:
    # Decrypting secrets back to plaintext would be a security regression.
    pass
