"""Export deterministic household-ingestion defects to SummitFlow tasks."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from app.config import PROJECT_ROOT
from app.logging_config import get_logger

logger = get_logger(__name__)

_TASK_ID_RE = re.compile(r"\btask-[0-9a-f]{8,}\b")
_FINAL_STATES = frozenset({"queued", "autocode_queued"})
_PROJECT_ID = PROJECT_ROOT.name


class HouseholdCodingIssueTaskService:
    """Queue coding repair tasks for deterministic ingestion defects."""

    def export_candidate(
        self,
        service: Any,
        *,
        document_id: str,
        candidate: dict[str, object] | None,
    ) -> dict[str, object]:
        if not candidate:
            existing = self._load_state(service, document_id=document_id)
            if existing:
                state: dict[str, object] = {
                    "status": "resolved",
                    "reason": "no_candidate",
                    "previous_status": str(existing.get("status") or ""),
                }
                task_id = existing.get("task_id")
                if isinstance(task_id, str) and task_id:
                    state["task_id"] = task_id
                self._store_state(service, document_id=document_id, state=state)
                return state
            return {"status": "skipped", "reason": "no_candidate"}

        signature = _candidate_signature(candidate)
        existing = self._load_state(service, document_id=document_id)
        if existing.get("signature") == signature:
            if str(existing.get("status") or "") in _FINAL_STATES:
                return existing
            task_id = existing.get("task_id")
            if isinstance(task_id, str) and task_id:
                return self._queue_existing_task(
                    service,
                    document_id=document_id,
                    candidate=candidate,
                    signature=signature,
                    task_id=task_id,
                )

        st_bin = shutil.which("st")
        if st_bin is None:
            state: dict[str, object] = {
                "status": "blocked",
                "reason": "st_unavailable",
                "signature": signature,
            }
            self._store_state(service, document_id=document_id, state=state)
            return state

        return self._create_and_queue_task(
            service,
            document_id=document_id,
            candidate=candidate,
            signature=signature,
            st_bin=st_bin,
        )

    def _create_and_queue_task(
        self,
        service: Any,
        *,
        document_id: str,
        candidate: dict[str, object],
        signature: str,
        st_bin: str,
    ) -> dict[str, object]:
        plan_path = self._write_plan(candidate)
        try:
            verify = _run_st([st_bin, "verify", str(plan_path)])
            if verify.returncode != 0:
                return self._store_failed(
                    service,
                    document_id=document_id,
                    signature=signature,
                    step="verify",
                    output=_combined_output(verify),
                )

            create = _run_st(
                [
                    st_bin,
                    "-P",
                    _project_id(candidate),
                    "create",
                    "--plan",
                    str(plan_path),
                ]
            )
            if create.returncode != 0:
                return self._store_failed(
                    service,
                    document_id=document_id,
                    signature=signature,
                    step="create",
                    output=_combined_output(create),
                )
            task_id = _extract_task_id(_combined_output(create))
            if not task_id:
                return self._store_failed(
                    service,
                    document_id=document_id,
                    signature=signature,
                    step="parse_task_id",
                    output=_combined_output(create),
                )

            autocode = _run_st(
                [
                    st_bin,
                    "-P",
                    _project_id(candidate),
                    "autocode",
                    task_id,
                ]
            )
            state: dict[str, object] = {
                "status": "queued" if autocode.returncode == 0 else "created",
                "signature": signature,
                "task_id": task_id,
                "autocode_queued": autocode.returncode == 0,
            }
            if autocode.returncode != 0:
                state["last_error"] = _truncate(_combined_output(autocode))
            self._store_state(service, document_id=document_id, state=state)
            return state
        finally:
            plan_path.unlink(missing_ok=True)

    def _queue_existing_task(
        self,
        service: Any,
        *,
        document_id: str,
        candidate: dict[str, object],
        signature: str,
        task_id: str,
    ) -> dict[str, object]:
        st_bin = shutil.which("st")
        if st_bin is None:
            state: dict[str, object] = {
                "status": "blocked",
                "reason": "st_unavailable",
                "signature": signature,
                "task_id": task_id,
            }
            self._store_state(service, document_id=document_id, state=state)
            return state
        autocode = _run_st([st_bin, "-P", _project_id(candidate), "autocode", task_id])
        state: dict[str, object] = {
            "status": "queued" if autocode.returncode == 0 else "created",
            "signature": signature,
            "task_id": task_id,
            "autocode_queued": autocode.returncode == 0,
        }
        if autocode.returncode != 0:
            state["last_error"] = _truncate(_combined_output(autocode))
        self._store_state(service, document_id=document_id, state=state)
        return state

    def _store_failed(
        self,
        service: Any,
        *,
        document_id: str,
        signature: str,
        step: str,
        output: str,
    ) -> dict[str, object]:
        state: dict[str, object] = {
            "status": "failed",
            "signature": signature,
            "step": step,
            "last_error": _truncate(output),
        }
        self._store_state(service, document_id=document_id, state=state)
        return state

    @staticmethod
    def _load_state(service: Any, *, document_id: str) -> dict[str, object]:
        with service.storage.connection() as conn:
            row = conn.execute(
                """
                SELECT metadata->'coding_issue_task'
                FROM household_documents
                WHERE id = %s
                """,
                [document_id],
            ).fetchone()
        if row is None:
            return {}
        value = row[0]
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _store_state(service: Any, *, document_id: str, state: dict[str, object]) -> None:
        with service.storage.connection() as conn:
            conn.execute(
                """
                UPDATE household_documents
                SET metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb
                WHERE id = %s
                """,
                [json.dumps({"coding_issue_task": state}), document_id],
            )
            conn.commit()

    @staticmethod
    def _write_plan(candidate: dict[str, object]) -> Path:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            suffix=".plan.json",
            prefix="household-ingestion-coding-issue-",
            delete=False,
        ) as handle:
            json.dump(_build_plan(candidate), handle, indent=2)
            handle.write("\n")
            return Path(handle.name)


def _build_plan(candidate: dict[str, object]) -> dict[str, object]:
    document_id = str(candidate.get("document_id") or "unknown")
    filename = str(candidate.get("filename") or "unknown document")
    raw_issue_codes = candidate.get("issue_codes", [])
    issue_codes = (
        [str(code) for code in raw_issue_codes if isinstance(code, str) and code]
        if isinstance(raw_issue_codes, list)
        else []
    ) or ["unknown"]
    acceptance = str(candidate.get("acceptance") or "").strip()
    return {
        "title": str(candidate.get("title") or f"Fix household ingestion for {filename}"),
        "objective": (
            "Fix deterministic household document ingestion reconciliation failures "
            f"for {filename}."
        ),
        "description": (
            "Generated by household document reconciliation after review/application. "
            f"Document id: {document_id}. Issue codes: {', '.join(issue_codes)}. "
            "Use the stored document as repro evidence; do not include document contents in task logs."
        ),
        "type": str(candidate.get("kind") or "bug"),
        "priority": 1,
        "complexity": "STANDARD",
        "labels": [
            _PROJECT_ID,
            "money",
            "household",
            "ingestion",
            "autocode",
        ],
        "spirit_anti": (
            "Do not add a broad ingestion framework, speculative retries, or runtime self-editing. "
            "Fix the smallest extractor/application/reconciliation defect proven by this document."
        ),
        "done_when": [
            acceptance
            or "Reprocess the stored document and verify reconciliation_summary.status is clear.",
            "Regression coverage proves the failure class stays fixed.",
            "Repo quality gates pass through st check.",
        ],
        "subtasks": [
            {
                "id": "1.1",
                "phase": "reproduce",
                "description": "Reproduce the reconciliation defect from the stored household document.",
                "steps": [
                    {
                        "description": "Load the document review, application summary, and reconciliation summary.",
                        "spec": {
                            "detail": (
                                f"Use document id {document_id}. Confirm issue codes: "
                                f"{', '.join(issue_codes)}."
                            )
                        },
                    },
                    {
                        "description": "Identify whether extraction, account evidence, transaction application, or registry sync caused the defect.",
                        "spec": {
                            "detail": "Do not guess from filename alone; inspect stored review data and applied rows."
                        },
                    },
                ],
            },
            {
                "id": "1.2",
                "phase": "fix",
                "description": "Patch the smallest proven ingestion defect.",
                "depends_on": ["1.1"],
                "steps": [
                    {
                        "description": "Update the narrow parser, reviewer normalization, application, or reconciliation code path that caused the defect.",
                        "spec": {
                            "detail": "Keep changes local to household document ingestion and avoid duplicate sources of truth."
                        },
                    },
                    {
                        "description": "Add focused regression coverage for the exact failure class.",
                        "spec": {
                            "detail": "Tests should fail before the patch and pass after it."
                        },
                    },
                ],
            },
            {
                "id": "1.3",
                "phase": "verify",
                "description": "Reprocess and verify the affected document.",
                "depends_on": ["1.2"],
                "steps": [
                    {
                        "description": "Reprocess the document and confirm reconciliation is clear.",
                        "spec": {
                            "detail": "Verify no coding_issue_candidate remains for this document after reprocessing."
                        },
                    },
                    {
                        "description": "Run repo quality gates through st check.",
                        "spec": {"detail": "Use the repo-standard st check wrapper."},
                    },
                ],
            },
        ],
    }


def _candidate_signature(candidate: dict[str, object]) -> str:
    payload = json.dumps(candidate, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _project_id(candidate: dict[str, object]) -> str:
    project = candidate.get("project")
    return str(project) if isinstance(project, str) and project else _PROJECT_ID


def _run_st(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=PROJECT_ROOT,
        env=_st_env(),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def _st_env() -> dict[str, str]:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    return env


def _combined_output(result: subprocess.CompletedProcess[str]) -> str:
    return "\n".join(part for part in (result.stdout, result.stderr) if part).strip()


def _extract_task_id(output: str) -> str | None:
    match = _TASK_ID_RE.search(output)
    return match.group(0) if match else None


def _truncate(value: str, limit: int = 2000) -> str:
    return value if len(value) <= limit else f"{value[:limit]}..."
