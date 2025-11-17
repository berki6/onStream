from pathlib import Path
import os

# Define project root (adjust based on your structure)
PROJECT_ROOT = Path(__file__).parent.parent.parent


def to_relative_path(absolute_path: Path) -> str:
    """Convert absolute Path to relative string with forward slashes."""
    try:
        relative = absolute_path.relative_to(PROJECT_ROOT)
        return str(relative).replace(os.sep, "/")
    except ValueError:
        # If not relative to project root, return as-is but normalized
        return str(absolute_path).replace(os.sep, "/")


def to_absolute_path(relative_path: str) -> Path:
    """Convert relative path string to absolute Path."""
    # Normalize separators to OS
    normalized = Path(relative_path.replace("/", os.sep))
    if normalized.is_absolute():
        return normalized
    return PROJECT_ROOT / normalized


def ensure_dir(path: Path) -> None:
    """Ensure directory exists."""
    path.parent.mkdir(parents=True, exist_ok=True)
