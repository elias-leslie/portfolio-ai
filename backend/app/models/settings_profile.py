"""Settings Profile models and database operations."""

from datetime import datetime
from typing import Any, Optional
from psycopg2.extensions import connection as Connection
from psycopg2.extras import RealDictCursor


class SettingsProfile:
    """Model for settings profiles."""

    def __init__(
        self,
        id: int,
        user_id: int,
        name: str,
        description: Optional[str],
        profile_data: dict[str, Any],
        is_active: bool,
        created_at: datetime,
        updated_at: datetime,
    ):
        self.id = id
        self.user_id = user_id
        self.name = name
        self.description = description
        self.profile_data = profile_data
        self.is_active = is_active
        self.created_at = created_at
        self.updated_at = updated_at

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "description": self.description,
            "profile_data": self.profile_data,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


def get_all_profiles(conn: Connection, user_id: int = 1) -> list[SettingsProfile]:
    """Get all profiles for a user."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT id, user_id, name, description, profile_data, is_active,
                   created_at, updated_at
            FROM settings_profiles
            WHERE user_id = %s
            ORDER BY is_active DESC, updated_at DESC
            """,
            (user_id,),
        )
        rows = cur.fetchall()
        return [SettingsProfile(**row) for row in rows]


def get_profile_by_id(
    conn: Connection, profile_id: int, user_id: int = 1
) -> Optional[SettingsProfile]:
    """Get a specific profile by ID."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT id, user_id, name, description, profile_data, is_active,
                   created_at, updated_at
            FROM settings_profiles
            WHERE id = %s AND user_id = %s
            """,
            (profile_id, user_id),
        )
        row = cur.fetchone()
        return SettingsProfile(**row) if row else None


def get_active_profile(conn: Connection, user_id: int = 1) -> Optional[SettingsProfile]:
    """Get the currently active profile for a user."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT id, user_id, name, description, profile_data, is_active,
                   created_at, updated_at
            FROM settings_profiles
            WHERE user_id = %s AND is_active = TRUE
            LIMIT 1
            """,
            (user_id,),
        )
        row = cur.fetchone()
        return SettingsProfile(**row) if row else None


def create_profile(
    conn: Connection,
    user_id: int,
    name: str,
    profile_data: dict[str, Any],
    description: Optional[str] = None,
    is_active: bool = False,
) -> SettingsProfile:
    """Create a new settings profile."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            INSERT INTO settings_profiles (user_id, name, description, profile_data, is_active)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id, user_id, name, description, profile_data, is_active,
                      created_at, updated_at
            """,
            (user_id, name, description, profile_data, is_active),
        )
        row = cur.fetchone()
        conn.commit()
        return SettingsProfile(**row)


def update_profile(
    conn: Connection,
    profile_id: int,
    user_id: int,
    name: Optional[str] = None,
    description: Optional[str] = None,
    profile_data: Optional[dict[str, Any]] = None,
    is_active: Optional[bool] = None,
) -> Optional[SettingsProfile]:
    """Update an existing profile."""
    # Build dynamic update query
    updates = []
    params: list[Any] = []

    if name is not None:
        updates.append(f"name = %s")
        params.append(name)
    if description is not None:
        updates.append(f"description = %s")
        params.append(description)
    if profile_data is not None:
        updates.append(f"profile_data = %s")
        params.append(profile_data)
    if is_active is not None:
        updates.append(f"is_active = %s")
        params.append(is_active)

    if not updates:
        return get_profile_by_id(conn, profile_id, user_id)

    params.extend([profile_id, user_id])

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            f"""
            UPDATE settings_profiles
            SET {', '.join(updates)}, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND user_id = %s
            RETURNING id, user_id, name, description, profile_data, is_active,
                      created_at, updated_at
            """,
            params,
        )
        row = cur.fetchone()
        conn.commit()
        return SettingsProfile(**row) if row else None


def delete_profile(conn: Connection, profile_id: int, user_id: int = 1) -> bool:
    """Delete a profile."""
    with conn.cursor() as cur:
        cur.execute(
            """
            DELETE FROM settings_profiles
            WHERE id = %s AND user_id = %s
            """,
            (profile_id, user_id),
        )
        deleted = cur.rowcount > 0
        conn.commit()
        return deleted


def activate_profile(conn: Connection, profile_id: int, user_id: int = 1) -> Optional[SettingsProfile]:
    """Activate a profile (deactivates all others automatically via trigger)."""
    return update_profile(conn, profile_id, user_id, is_active=True)


def duplicate_profile(
    conn: Connection,
    profile_id: int,
    new_name: str,
    user_id: int = 1,
) -> Optional[SettingsProfile]:
    """Duplicate an existing profile with a new name."""
    original = get_profile_by_id(conn, profile_id, user_id)
    if not original:
        return None

    return create_profile(
        conn,
        user_id=user_id,
        name=new_name,
        description=f"Copy of {original.name}",
        profile_data=original.profile_data,
        is_active=False,
    )
