import sys
import json

# Add backend to path
sys.path.append("/home/kasadis/portfolio-ai/backend")

from app.services.artifact_manager import save_artifact
from app.services.artifact_manager import ARTIFACTS_BASE_DIR


def register_version(feature_id, criterion_id, version):
    print(f"Registering version {version} for {feature_id}/{criterion_id}...")

    artifact_dir = f"{feature_id}/{criterion_id}/v{version}"
    abs_path = ARTIFACTS_BASE_DIR / artifact_dir
    evidence_path = abs_path / "evidence.json"
    screenshot_path = abs_path / "screenshot.png"

    if not evidence_path.exists():
        print(f"Evidence file not found: {evidence_path}")
        return

    try:
        with open(evidence_path, "r") as f:
            evidence_data = json.load(f)

        screenshot_size = (
            screenshot_path.stat().st_size if screenshot_path.exists() else 0
        )
        evidence_size = evidence_path.stat().st_size
        total_size = screenshot_size + evidence_size

        save_artifact(
            feature_id=feature_id,
            criterion_id=criterion_id,
            version=version,
            file_path=artifact_dir,
            file_size_bytes=total_size,
            evidence_data=evidence_data,
            expires_hours=240,  # 10 days
        )
        print(f"Successfully registered v{version}")
    except Exception as e:
        print(f"Failed to register v{version}: {e}")


if __name__ == "__main__":
    # Register accumulated versions
    register_version("FEAT-110", "ac-001", 2)
    register_version("FEAT-110", "ac-001", 3)
    register_version("FEAT-110", "ac-001", 4)
