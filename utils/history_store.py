"""Local, file-based decision history so completed decisions survive a page refresh.

Records are stored as JSON lines in `data/decision_history.jsonl` (override the
folder with CIPHERBRIDGE_DATA_DIR). Everything stays on this machine. Do not
enter secrets into topics: transcripts are saved as written."""
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from utils.paths import data_dir


def _path() -> Path:
    return data_dir() / "decision_history.jsonl"


def _read_all() -> List[Dict]:
    path = _path()
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue  # skip a corrupt line rather than losing the whole history
        if isinstance(record, dict) and record.get("id"):
            records.append(record)
    return records


def _write_all(records: List[Dict]) -> None:
    path = _path()
    tmp = path.with_suffix(".tmp")
    tmp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")
    os.replace(tmp, path)


def save_result(result: Dict) -> str:
    """Append a completed decision and return its id."""
    record = dict(result)
    record["id"] = uuid.uuid4().hex[:8]
    record["saved_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _path().open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record["id"]


def list_history(limit: Optional[int] = None) -> List[Dict]:
    """Saved decisions, newest first."""
    records = list(reversed(_read_all()))
    return records[:limit] if limit else records


def get_result(record_id: str) -> Optional[Dict]:
    return next((r for r in _read_all() if r["id"] == record_id), None)


def delete_result(record_id: str) -> bool:
    records = _read_all()
    kept = [r for r in records if r["id"] != record_id]
    if len(kept) == len(records):
        return False
    _write_all(kept)
    return True


def clear_history() -> int:
    count = len(_read_all())
    _write_all([])
    return count
