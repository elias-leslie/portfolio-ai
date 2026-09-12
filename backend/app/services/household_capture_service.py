"""Small durable evidence queue. Uploads never create financial transactions."""

from __future__ import annotations

import hashlib
import uuid
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from app.config import settings
from app.models.household_capture import CaptureReview, CaptureView
from app.services.household_document_storage import resolve_upload_path
from app.services.household_identity import HouseholdIdentity, require_adult
from app.storage import get_storage

_SELECT = """SELECT c.id, c.captured_by, coalesce(m.display_name, 'Local workspace'), c.kind,
    c.filename, c.store_name, c.note, c.status, c.outcome, c.purchased_by, c.purchased_for,
    c.document_id, c.review_note, c.created_at, c.storage_key, c.content_type, c.content_sha256,
    d.metadata -> 'application_summary' ->> 'status', d.review_status
    FROM household_captures c LEFT JOIN household_members m ON m.id = c.captured_by
    LEFT JOIN household_documents d ON d.id = c.document_id"""


def _view(row: Any) -> CaptureView:
    status = row[7]
    if status == "in_review":
        if row[17] == "applied" and row[18] == "complete":
            status = "verified"
        elif row[11] is None or row[18] == "failed":
            status = "needs_correction"
    return CaptureView(
        id=str(row[0]),
        captured_by=str(row[1]) if row[1] else None,
        captured_by_name=row[2],
        kind=row[3],
        filename=row[4],
        store_name=row[5],
        note=row[6],
        status=status,
        outcome=row[8],
        purchased_by=str(row[9]) if row[9] else None,
        purchased_for=str(row[10]) if row[10] else None,
        document_id=str(row[11]) if row[11] else None,
        review_note=row[12],
        created_at=row[13].isoformat(),
    )


class HouseholdCaptureService:
    def __init__(self) -> None:
        self.storage = get_storage()

    def list_captures(self, identity: HouseholdIdentity) -> list[CaptureView]:
        where = " WHERE c.captured_by = %s" if identity.access == "capture_only" else ""
        params = [identity.member_id] if where else []
        with self.storage.connection() as conn:
            rows = conn.execute(
                _SELECT + where + " ORDER BY c.created_at DESC LIMIT 100", params
            ).fetchall()
        return [_view(row) for row in rows]

    def _row(self, identity: HouseholdIdentity, capture_id: str) -> Any:
        with self.storage.connection() as conn:
            row = conn.execute(_SELECT + " WHERE c.id = %s", [capture_id]).fetchone()
        if row is None or (identity.access == "capture_only" and str(row[1]) != identity.member_id):
            raise HTTPException(404, "Capture not found.")
        return row

    def get(self, identity: HouseholdIdentity, capture_id: str) -> CaptureView:
        return _view(self._row(identity, capture_id))

    def image(self, identity: HouseholdIdentity, capture_id: str) -> tuple[Path, str]:
        row = self._row(identity, capture_id)
        path = resolve_upload_path(row[14], settings.household_upload_dir)
        if path is None:
            raise HTTPException(404, "This capture's image is unavailable. Please upload it again.")
        return path, row[15]

    def save(
        self,
        identity: HouseholdIdentity,
        *,
        client_id: str,
        kind: str,
        content: bytes,
        filename: str,
        content_type: str,
        store_name: str,
        note: str,
    ) -> CaptureView:
        digest = hashlib.sha256(content).hexdigest()
        capture_id = str(uuid.uuid4())
        suffix = Path(filename).suffix.lower()
        key = f"captures/{capture_id}{suffix}"
        path = settings.household_upload_dir / key
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        path.write_bytes(content)
        path.chmod(0o600)
        try:
            with self.storage.connection() as conn:
                row = conn.execute(
                    """INSERT INTO household_captures
                    (id, captured_by, client_id, kind, filename, storage_key, content_type,
                     content_sha256, store_name, note)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (captured_by, client_id) DO NOTHING RETURNING id""",
                    [
                        capture_id,
                        identity.member_id,
                        client_id,
                        kind,
                        Path(filename).name,
                        key,
                        content_type,
                        digest,
                        store_name.strip(),
                        note.strip(),
                    ],
                ).fetchone()
                if row is None:
                    existing = conn.execute(
                        """SELECT id, content_sha256, kind FROM household_captures
                        WHERE captured_by IS NOT DISTINCT FROM %s AND client_id = %s""",
                        [identity.member_id, client_id],
                    ).fetchone()
                    if existing is None or existing[1] != digest or existing[2] != kind:
                        raise HTTPException(
                            409, "This draft was already uploaded with different contents."
                        )
                    capture_id = str(existing[0])
                    path.unlink(missing_ok=True)
                conn.commit()
        except Exception:
            path.unlink(missing_ok=True)
            raise
        return self.get(identity, capture_id)

    def review(
        self, identity: HouseholdIdentity, capture_id: str, payload: CaptureReview
    ) -> CaptureView:
        require_adult(identity)
        self._row(identity, capture_id)
        with self.storage.connection() as conn:
            for member in (payload.purchased_by, payload.purchased_for):
                if (
                    member
                    and not conn.execute(
                        "SELECT 1 FROM household_members WHERE id = %s", [str(member)]
                    ).fetchone()
                ):
                    raise HTTPException(422, "Choose an existing household member.")
            conn.execute(
                """UPDATE household_captures SET status=%s, outcome=%s, purchased_by=%s,
                purchased_for=%s, review_note=%s, reviewed_by=%s, updated_at=now() WHERE id=%s""",
                [
                    payload.status,
                    payload.outcome,
                    str(payload.purchased_by) if payload.purchased_by else None,
                    str(payload.purchased_for) if payload.purchased_for else None,
                    payload.review_note,
                    identity.member_id,
                    capture_id,
                ],
            )
            conn.commit()
        return self.get(identity, capture_id)

    def attach_document(
        self, identity: HouseholdIdentity, capture_id: str, document_id: str
    ) -> CaptureView:
        require_adult(identity)
        self._row(identity, capture_id)
        with self.storage.connection() as conn:
            conn.execute(
                "UPDATE household_captures SET document_id=%s, status='in_review', updated_at=now() WHERE id=%s",
                [document_id, capture_id],
            )
            conn.commit()
        return self.get(identity, capture_id)
