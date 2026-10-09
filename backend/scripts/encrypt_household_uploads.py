#!/usr/bin/env python3
"""Encrypt legacy plaintext household uploads in place.

New statements, receipts and evidence are encrypted at write time
(app/services/household_upload_crypto.py). Files stored before that change are
still plaintext; readers accept both, so this one-time migration can run at any
time without downtime.

Behavior:
  * Idempotent: files that already carry the encryption marker are skipped.
  * Atomic: each file is encrypted, verified by decrypting back to the same
    bytes, written to an fsynced 0600 sibling temp file, then renamed over the
    original. A crash leaves either the old plaintext or the new ciphertext.
  * Digests are unaffected: content_sha256 in the database is computed over
    plaintext, and readers decrypt before hashing or parsing.
  * Symlinks, non-regular files and in-flight ``*.tmp`` files are skipped.

Requires PORTFOLIO_SECRET_KEY (the same key the backend uses). Keep that key
with backups: encrypted uploads cannot be read without it.

Usage:
    cd ~/portfolio-ai/backend
    .venv/bin/python scripts/encrypt_household_uploads.py --dry-run
    .venv/bin/python scripts/encrypt_household_uploads.py
    .venv/bin/python scripts/encrypt_household_uploads.py --upload-dir /path/to/household_uploads
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.services.household_upload_crypto import (
    decrypt_upload_bytes,
    encrypt_upload_bytes,
    is_encrypted_upload,
    write_private_file_atomic,
)


def encrypt_upload_tree(upload_root: Path, *, dry_run: bool = False) -> dict[str, int]:
    """Encrypt every plaintext upload under ``upload_root``; return counts."""
    counts = {"encrypted": 0, "already_encrypted": 0, "skipped": 0}
    if not upload_root.is_dir():
        return counts
    for path in sorted(upload_root.rglob("*")):
        if path.is_symlink() or (path.is_file() and path.name.endswith(".tmp")):
            counts["skipped"] += 1
            continue
        if not path.is_file():
            continue
        plaintext = path.read_bytes()
        if is_encrypted_upload(plaintext):
            counts["already_encrypted"] += 1
            continue
        ciphertext = encrypt_upload_bytes(plaintext)
        if decrypt_upload_bytes(ciphertext) != plaintext:
            raise RuntimeError(f"Encryption round-trip failed for {path.name}; nothing written")
        if not dry_run:
            write_private_file_atomic(path, ciphertext)
        counts["encrypted"] += 1
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--upload-dir",
        type=Path,
        default=settings.household_upload_dir,
        help="Household upload root (default: configured HOUSEHOLD_UPLOAD_DIR)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Count files without writing")
    args = parser.parse_args()
    counts = encrypt_upload_tree(args.upload_dir.resolve(), dry_run=args.dry_run)
    verb = "would encrypt" if args.dry_run else "encrypted"
    print(
        f"{verb} {counts['encrypted']} file(s); "
        f"{counts['already_encrypted']} already encrypted; {counts['skipped']} skipped"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
