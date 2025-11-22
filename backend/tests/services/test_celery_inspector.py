"""Tests for Celery inspection service."""

from unittest.mock import MagicMock, patch

from app.services.celery_inspector import (
    get_active_tasks,
    get_pending_tasks,
    get_queue_depth,
    get_recent_completed,
    get_recent_failed,
    get_unified_task_list,
)


class TestGetActiveTasks:
    """Test get_active_tasks function."""

    def test_get_active_tasks_returns_list_of_active_tasks(self) -> None:
        """Test that get_active_tasks returns list of active tasks."""
        # Arrange: Mock Celery inspect API
        with patch("app.services.celery_inspector.celery_app") as mock_celery:
            mock_inspect = MagicMock()
            mock_celery.control.inspect.return_value = mock_inspect

            # Simulate active tasks response
            mock_inspect.active.return_value = {
                "celery@worker1": [
                    {
                        "id": "task-123",
                        "name": "app.tasks.watchlist_tasks.refresh_watchlist_scores",
                        "args": "[]",
                        "kwargs": "{}",
                        "time_start": 1699000000.0,
                        "worker_pid": 12345,
                    }
                ]
            }

            # Act
            result = get_active_tasks()

            # Assert
            assert isinstance(result, list)
            assert len(result) == 1
            assert result[0]["id"] == "task-123"
            assert result[0]["status"] == "ACTIVE"
            assert "refresh_watchlist_scores" in result[0]["name"]


class TestGetPendingTasks:
    """Test get_pending_tasks function."""

    def test_get_pending_tasks_returns_list_of_pending_tasks(self) -> None:
        """Test that get_pending_tasks returns list of pending/reserved tasks."""
        # Arrange
        with patch("app.services.celery_inspector.celery_app") as mock_celery:
            mock_inspect = MagicMock()
            mock_celery.control.inspect.return_value = mock_inspect

            # Simulate reserved tasks response
            mock_inspect.reserved.return_value = {
                "celery@worker1": [
                    {
                        "id": "task-456",
                        "name": "app.tasks.agent_tasks.run_agent",
                        "args": "[1]",
                        "kwargs": "{}",
                    }
                ]
            }

            # Act
            result = get_pending_tasks()

            # Assert
            assert isinstance(result, list)
            assert len(result) == 1
            assert result[0]["id"] == "task-456"
            assert result[0]["status"] == "PENDING"


class TestGetRecentCompleted:
    """Test get_recent_completed function."""

    def test_get_recent_completed_queries_taskmeta_table(
        self,
    ) -> None:
        """Test that get_recent_completed queries celery_taskmeta table."""
        # Arrange: Insert test data using ConnectionManager
        from app.storage.connection import ConnectionManager

        cm = ConnectionManager()

        with cm.connection() as conn:
            conn.execute(
                """
                INSERT INTO celery_taskmeta (id, task_id, status, result, date_done, traceback)
                VALUES
                    (1, 'completed-1', 'SUCCESS', '"result data"', NOW() - INTERVAL '1 minute', NULL),
                    (2, 'completed-2', 'SUCCESS', '"result data"', NOW() - INTERVAL '2 minutes', NULL),
                    (3, 'failed-1', 'FAILURE', NULL, NOW() - INTERVAL '1 minute', 'Error trace')
            """,
                [],
            )
            conn.commit()

        # Act
        result = get_recent_completed(limit=10)

        # Assert
        assert isinstance(result, list)
        assert len(result) >= 2
        # Most recent should be first
        assert result[0]["task_id"] == "completed-1"
        assert result[0]["status"] == "SUCCESS"


class TestGetRecentFailed:
    """Test get_recent_failed function."""

    def test_get_recent_failed_queries_failed_tasks(
        self,
    ) -> None:
        """Test that get_recent_failed returns only failed tasks."""
        # Arrange: Insert test data using ConnectionManager
        from app.storage.connection import ConnectionManager

        cm = ConnectionManager()

        with cm.connection() as conn:
            conn.execute(
                """
                INSERT INTO celery_taskmeta (id, task_id, status, result, date_done, traceback)
                VALUES
                    (4, 'failed-2', 'FAILURE', NULL, NOW() - INTERVAL '1 minute', 'Error trace 2'),
                    (5, 'failed-3', 'FAILURE', NULL, NOW() - INTERVAL '2 minutes', 'Error trace 3')
            """,
                [],
            )
            conn.commit()

        # Act
        result = get_recent_failed(limit=10)

        # Assert
        assert isinstance(result, list)
        assert len(result) >= 2
        assert all(task["status"] == "FAILURE" for task in result)


class TestGetQueueDepth:
    """Test get_queue_depth function."""

    def test_get_queue_depth_calculates_pending_task_count(self) -> None:
        """Test that get_queue_depth returns count of pending tasks."""
        # Arrange
        with patch("app.services.celery_inspector.celery_app") as mock_celery:
            mock_inspect = MagicMock()
            mock_celery.control.inspect.return_value = mock_inspect

            # Simulate reserved tasks across multiple workers
            mock_inspect.reserved.return_value = {
                "celery@worker1": [
                    {"id": "task-1", "name": "app.tasks.task1"},
                    {"id": "task-2", "name": "app.tasks.task2"},
                ],
                "celery@worker2": [{"id": "task-3", "name": "app.tasks.task3"}],
            }

            # Act
            result = get_queue_depth()

            # Assert
            assert result == 3


class TestGetUnifiedTaskList:
    """Test get_unified_task_list function."""

    def test_get_unified_task_list_merges_all_sources(
        self,
    ) -> None:
        """Test that get_unified_task_list merges active, pending, completed, failed."""
        # Arrange: Insert completed/failed tasks using ConnectionManager
        from app.storage.connection import ConnectionManager

        cm = ConnectionManager()

        with cm.connection() as conn:
            conn.execute(
                """
                INSERT INTO celery_taskmeta (id, task_id, status, result, date_done, traceback)
                VALUES
                    (6, 'unified-completed', 'SUCCESS', '"result"', NOW() - INTERVAL '1 minute', NULL),
                    (7, 'unified-failed', 'FAILURE', NULL, NOW() - INTERVAL '1 minute', 'Error')
            """,
                [],
            )
            conn.commit()

        # Mock active and pending
        with (
            patch("app.services.celery_inspector.get_active_tasks") as mock_active,
            patch("app.services.celery_inspector.get_pending_tasks") as mock_pending,
        ):
            mock_active.return_value = [{"id": "active-1", "status": "ACTIVE"}]
            mock_pending.return_value = [{"id": "pending-1", "status": "PENDING"}]

            # Act
            result = get_unified_task_list(status="all", limit=50)

            # Assert
            assert isinstance(result, list)
            assert len(result) >= 4  # active + pending + completed + failed

    def test_get_unified_task_list_filters_by_status(
        self,
    ) -> None:
        """Test that get_unified_task_list filters by status parameter."""
        # Arrange
        with (
            patch("app.services.celery_inspector.get_active_tasks") as mock_active,
            patch("app.services.celery_inspector.get_pending_tasks") as mock_pending,
        ):
            mock_active.return_value = [{"id": "active-1", "status": "ACTIVE"}]
            mock_pending.return_value = [{"id": "pending-1", "status": "PENDING"}]

            # Act: Filter for active only
            result = get_unified_task_list(status="active", limit=50)

            # Assert
            assert len(result) == 1
            assert result[0]["status"] == "ACTIVE"
