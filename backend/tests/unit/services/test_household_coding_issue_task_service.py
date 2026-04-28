"""Unit tests for household coding issue task export."""

from __future__ import annotations

from subprocess import CompletedProcess
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.household_coding_issue_task_service import (
    HouseholdCodingIssueTaskService,
    _build_plan,
    _run_st,
)


def _candidate() -> dict[str, object]:
    return {
        "title": "Fix household document ingestion audit failures for statement.csv",
        "kind": "bug",
        "project": "portfolio-ai",
        "component": "household_document_ingestion",
        "document_id": "doc-1",
        "filename": "statement.csv",
        "issue_codes": ["invalid_numeric_field"],
        "acceptance": "Reprocess the document and verify reconciliation_summary.status is clear.",
    }


def _service_with_state(state: dict[str, object] | None = None) -> tuple[object, MagicMock]:
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = (state,)
    storage = MagicMock()
    storage.connection.return_value.__enter__.return_value = conn
    return SimpleNamespace(storage=storage), conn


def test_export_candidate_creates_plan_task_and_queues_autocode() -> None:
    service, conn = _service_with_state()
    completed = [
        CompletedProcess(["st"], 0, "verified", ""),
        CompletedProcess(["st"], 0, "created task-1234abcd", ""),
        CompletedProcess(["st"], 0, "queued", ""),
    ]

    with (
        patch(
            "app.services.household_coding_issue_task_service.shutil.which",
            return_value="/usr/bin/st",
        ),
        patch(
            "app.services.household_coding_issue_task_service.subprocess.run",
            side_effect=completed,
        ) as run,
    ):
        state = HouseholdCodingIssueTaskService().export_candidate(
            service,
            document_id="doc-1",
            candidate=_candidate(),
        )

    assert state["status"] == "queued"
    assert state["task_id"] == "task-1234abcd"
    assert state["autocode_queued"] is True
    commands = [call.args[0] for call in run.call_args_list]
    assert commands[0][1] == "verify"
    assert commands[1][1:4] == ["-P", "portfolio-ai", "create"]
    assert commands[2][1:4] == ["-P", "portfolio-ai", "autocode"]
    assert conn.commit.called


def test_export_candidate_blocks_cleanly_when_st_unavailable() -> None:
    service, conn = _service_with_state()

    with patch(
        "app.services.household_coding_issue_task_service.shutil.which",
        return_value=None,
    ):
        state = HouseholdCodingIssueTaskService().export_candidate(
            service,
            document_id="doc-1",
            candidate=_candidate(),
        )

    assert state["status"] == "blocked"
    assert state["reason"] == "st_unavailable"
    assert conn.commit.called


def test_export_candidate_marks_existing_issue_resolved_when_candidate_clears() -> None:
    service, conn = _service_with_state(
        {
            "status": "failed",
            "signature": "abc123",
            "task_id": "task-1234abcd",
        }
    )

    state = HouseholdCodingIssueTaskService().export_candidate(
        service,
        document_id="doc-1",
        candidate=None,
    )

    assert state == {
        "status": "resolved",
        "reason": "no_candidate",
        "previous_status": "failed",
        "task_id": "task-1234abcd",
    }
    assert conn.commit.called


def test_export_candidate_skips_already_queued_signature() -> None:
    existing = {
        "status": "queued",
        "signature": "abc123",
        "task_id": "task-1234abcd",
    }
    service, conn = _service_with_state(existing)

    with (
        patch(
            "app.services.household_coding_issue_task_service._candidate_signature",
            return_value="abc123",
        ),
        patch("app.services.household_coding_issue_task_service.subprocess.run") as run,
    ):
        state = HouseholdCodingIssueTaskService().export_candidate(
            service,
            document_id="doc-1",
            candidate=_candidate(),
        )

    assert state == existing
    run.assert_not_called()
    assert not conn.commit.called


def test_build_plan_has_execution_ready_repair_shape() -> None:
    plan = _build_plan(_candidate())

    assert plan["type"] == "bug"
    assert "household" in plan["labels"]
    assert "runtime self-editing" in plan["spirit_anti"]
    subtasks = plan["subtasks"]
    assert isinstance(subtasks, list)
    first = subtasks[0]
    last = subtasks[-1]
    assert isinstance(first, dict)
    assert isinstance(last, dict)
    assert first["phase"] == "reproduce"
    assert last["phase"] == "verify"


def test_run_st_does_not_leak_backend_pythonpath() -> None:
    with (
        patch.dict("os.environ", {"PYTHONPATH": "/srv/workspaces/projects/portfolio-ai/backend"}),
        patch(
            "app.services.household_coding_issue_task_service.subprocess.run",
            return_value=CompletedProcess(["st"], 0, "", ""),
        ) as run,
    ):
        _run_st(["st", "verify", "plan.json"])

    env = run.call_args.kwargs["env"]
    assert "PYTHONPATH" not in env
    assert "PYTHONHOME" not in env
