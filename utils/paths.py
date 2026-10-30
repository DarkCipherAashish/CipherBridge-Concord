"""Shared filesystem locations (overridable with environment variables for tests)."""
import os
from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def data_dir(create: bool = True) -> Path:
    """Local data folder (history, user knowledge). Override with CIPHERBRIDGE_DATA_DIR."""
    folder = Path(os.getenv("CIPHERBRIDGE_DATA_DIR") or project_root() / "data")
    if create:
        folder.mkdir(parents=True, exist_ok=True)
    return folder


def curated_knowledge_dir() -> Path:
    """Shipped starter notes. Override with CIPHERBRIDGE_KB_DIR."""
    return Path(os.getenv("CIPHERBRIDGE_KB_DIR") or project_root() / "knowledge_base")


def user_knowledge_dir(create: bool = False) -> Path:
    folder = data_dir(create=create) / "knowledge"
    if create:
        folder.mkdir(parents=True, exist_ok=True)
    return folder
