"""Authentication credential resolution for REST API sources.

Handles multiple credential placeholder formats and auth methods.
"""

from __future__ import annotations


def resolve_auth_credentials(
    auth_config: dict[str, object], credentials: dict[str, str]
) -> dict[str, object]:
    """Replace credential placeholders with actual values.

    Supported formats:
    - {{secret.source/field}} or {{secret:source:field}} (placeholder)
    - {"credential_field": "apiKey"} (direct field reference)
    - {"type": "query", "query_param": "apikey"} (infer from param name)

    Args:
        auth_config: Auth configuration with potential placeholders
        credentials: Dict of credential field → value pairs

    Returns:
        Resolved auth configuration with actual credential values
    """
    resolved: dict[str, object] = dict(auth_config)

    # Method 1: Resolve placeholder in value field
    if "value" in resolved:
        value = resolved["value"]
        if isinstance(value, str) and "{{secret" in value:
            placeholder = value.strip("{}")

            # Handle both dot and colon notation
            if ":" in placeholder:
                parts = placeholder.split(":")
                field = parts[2] if len(parts) == 3 else parts[-1]
            else:
                _, source_field = placeholder.split(".", 1)
                _, field = source_field.rsplit("/", 1)

            resolved["value"] = credentials.get(field, value)

    # Method 2: Resolve using credential_field
    elif "credential_field" in resolved:
        field = str(resolved["credential_field"])
        if field in credentials:
            resolved["value"] = credentials[field]

    # Method 3: Infer from query_param or key_name
    elif "query_param" in resolved or "key_name" in resolved:
        param_name = str(resolved.get("query_param") or resolved.get("key_name", ""))
        if param_name in credentials:
            resolved["value"] = credentials[param_name]
        else:
            # Try case-insensitive match
            for cred_key, cred_val in credentials.items():
                if cred_key.lower() == param_name.lower():
                    resolved["value"] = cred_val
                    break

    return resolved
