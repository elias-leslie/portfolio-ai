"""Settings Profiles API routes.

Note: This is legacy Flask code. Use app/api/settings_profiles.py (FastAPI) instead.
"""

from __future__ import annotations

# mypy: ignore-errors
from typing import Any

from flask import Blueprint, jsonify, request  # type: ignore[import-not-found]

from app.database import get_db_connection  # type: ignore[import-not-found]
from app.models.settings_profile import (
    activate_profile,
    create_profile,
    delete_profile,
    duplicate_profile,
    get_active_profile,
    get_all_profiles,
    get_profile_by_id,
    update_profile,
)

settings_profiles_bp = Blueprint("settings_profiles", __name__)


@settings_profiles_bp.route("/api/settings/profiles", methods=["GET"])
def list_profiles() -> Any:
    """Get all settings profiles for the user."""
    user_id = request.args.get("user_id", 1, type=int)

    try:
        conn = get_db_connection()
        profiles = get_all_profiles(conn, user_id)
        conn.close()

        return jsonify([p.to_dict() for p in profiles]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@settings_profiles_bp.route("/api/settings/profiles/<int:profile_id>", methods=["GET"])
def get_profile(profile_id: int) -> Any:
    """Get a specific profile."""
    user_id = request.args.get("user_id", 1, type=int)

    try:
        conn = get_db_connection()
        profile = get_profile_by_id(conn, profile_id, user_id)
        conn.close()

        if not profile:
            return jsonify({"error": "Profile not found"}), 404

        return jsonify(profile.to_dict()), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@settings_profiles_bp.route("/api/settings/profiles/active", methods=["GET"])
def get_active() -> Any:
    """Get the currently active profile."""
    user_id = request.args.get("user_id", 1, type=int)

    try:
        conn = get_db_connection()
        profile = get_active_profile(conn, user_id)
        conn.close()

        if not profile:
            return jsonify({"error": "No active profile"}), 404

        return jsonify(profile.to_dict()), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@settings_profiles_bp.route("/api/settings/profiles", methods=["POST"])
def create() -> Any:
    """Create a new settings profile."""
    data = request.get_json()
    user_id = data.get("user_id", 1)

    if not data.get("name"):
        return jsonify({"error": "Profile name is required"}), 400
    if not data.get("profile_data"):
        return jsonify({"error": "Profile data is required"}), 400

    try:
        conn = get_db_connection()
        profile = create_profile(
            conn,
            user_id=user_id,
            name=data["name"],
            profile_data=data["profile_data"],
            description=data.get("description"),
            is_active=data.get("is_active", False),
        )
        conn.close()

        return jsonify(profile.to_dict()), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@settings_profiles_bp.route("/api/settings/profiles/<int:profile_id>", methods=["PUT"])
def update(profile_id: int) -> Any:
    """Update an existing profile."""
    data = request.get_json()
    user_id = data.get("user_id", 1)

    try:
        conn = get_db_connection()
        profile = update_profile(
            conn,
            profile_id=profile_id,
            user_id=user_id,
            name=data.get("name"),
            description=data.get("description"),
            profile_data=data.get("profile_data"),
            is_active=data.get("is_active"),
        )
        conn.close()

        if not profile:
            return jsonify({"error": "Profile not found"}), 404

        return jsonify(profile.to_dict()), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@settings_profiles_bp.route("/api/settings/profiles/<int:profile_id>", methods=["DELETE"])
def delete(profile_id: int) -> Any:
    """Delete a profile."""
    user_id = request.args.get("user_id", 1, type=int)

    try:
        conn = get_db_connection()
        deleted = delete_profile(conn, profile_id, user_id)
        conn.close()

        if not deleted:
            return jsonify({"error": "Profile not found"}), 404

        return jsonify({"message": "Profile deleted successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@settings_profiles_bp.route("/api/settings/profiles/<int:profile_id>/activate", methods=["POST"])
def activate(profile_id: int) -> Any:
    """Activate a profile."""
    user_id = request.args.get("user_id", 1, type=int)

    try:
        conn = get_db_connection()
        profile = activate_profile(conn, profile_id, user_id)
        conn.close()

        if not profile:
            return jsonify({"error": "Profile not found"}), 404

        return jsonify(profile.to_dict()), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@settings_profiles_bp.route("/api/settings/profiles/<int:profile_id>/duplicate", methods=["POST"])
def duplicate(profile_id: int) -> Any:
    """Duplicate a profile."""
    data = request.get_json()
    user_id = data.get("user_id", 1)
    new_name = data.get("name")

    if not new_name:
        return jsonify({"error": "New profile name is required"}), 400

    try:
        conn = get_db_connection()
        profile = duplicate_profile(conn, profile_id, new_name, user_id)
        conn.close()

        if not profile:
            return jsonify({"error": "Original profile not found"}), 404

        return jsonify(profile.to_dict()), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@settings_profiles_bp.route("/api/settings/profiles/<int:profile_id>/export", methods=["GET"])
def export_profile(profile_id: int) -> Any:
    """Export a profile as JSON for sharing/backup."""
    user_id = request.args.get("user_id", 1, type=int)

    try:
        conn = get_db_connection()
        profile = get_profile_by_id(conn, profile_id, user_id)
        conn.close()

        if not profile:
            return jsonify({"error": "Profile not found"}), 404

        # Export format includes metadata
        export_data = {
            "name": profile.name,
            "description": profile.description,
            "profile_data": profile.profile_data,
            "exported_at": profile.updated_at.isoformat(),
            "version": "1.0",
        }

        return jsonify(export_data), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@settings_profiles_bp.route("/api/settings/profiles/import", methods=["POST"])
def import_profile() -> Any:
    """Import a profile from exported JSON."""
    data = request.get_json()
    user_id = data.get("user_id", 1)

    if not data.get("name"):
        return jsonify({"error": "Profile name is required"}), 400
    if not data.get("profile_data"):
        return jsonify({"error": "Profile data is required"}), 400

    try:
        conn = get_db_connection()
        profile = create_profile(
            conn,
            user_id=user_id,
            name=data["name"],
            profile_data=data["profile_data"],
            description=data.get("description", "Imported profile"),
            is_active=False,
        )
        conn.close()

        return jsonify(profile.to_dict()), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500
