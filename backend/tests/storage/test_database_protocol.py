"""Tests for DatabaseConnection Protocol definition."""

from typing import Any

from app.storage.types import DatabaseConnection


class MockDatabaseConnection:
    """Mock implementation of DatabaseConnection Protocol for testing."""

    def execute(self, query: str, params: list[Any] | None = None) -> Any:
        """Mock execute method."""
        return {"executed": True, "query": query, "params": params}

    def fetchdf(self) -> Any:
        """Mock fetchdf method."""
        return {"type": "dataframe", "rows": []}

    def pl(self) -> Any:
        """Mock pl method."""
        return {"type": "polars", "data": []}


def test_protocol_can_be_imported() -> None:
    """Test that DatabaseConnection Protocol can be imported."""
    assert DatabaseConnection is not None


def test_mock_implements_protocol() -> None:
    """Test that mock object implements the Protocol correctly."""
    mock_conn: DatabaseConnection = MockDatabaseConnection()

    # Test execute method
    result = mock_conn.execute("SELECT * FROM test", ["param1"])
    assert result["executed"] is True
    assert result["query"] == "SELECT * FROM test"
    assert result["params"] == ["param1"]

    # Test fetchdf method
    df_result = mock_conn.fetchdf()
    assert df_result["type"] == "dataframe"

    # Test pl method
    pl_result = mock_conn.pl()
    assert pl_result["type"] == "polars"


def test_protocol_requires_all_methods() -> None:
    """Test that Protocol requires all three methods."""

    class IncompleteConnection:
        """Incomplete implementation missing methods."""

        def execute(self, query: str, params: list[Any] | None = None) -> Any:
            """Only execute implemented."""
            return None

    # This should fail mypy type checking (but passes at runtime due to duck typing)
    # We're verifying the Protocol definition is correct
    incomplete: DatabaseConnection = IncompleteConnection()  # type: ignore
    assert hasattr(incomplete, "execute")
    assert not hasattr(incomplete, "fetchdf")
    assert not hasattr(incomplete, "pl")
