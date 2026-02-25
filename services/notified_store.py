import json
import logging
from pathlib import Path

STORE_FILE = Path("data/notified.json")
_store: dict = {}


def _load():
    global _store
    if STORE_FILE.exists():
        try:
            _store = json.loads(STORE_FILE.read_text(encoding="utf-8"))
        except Exception:
            _store = {}


def _save():
    import shutil
    import tempfile
    STORE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STORE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(_store), encoding="utf-8")
    shutil.move(str(tmp), str(STORE_FILE))


_load()


def is_notified(record_id, event: str) -> bool:
    return _store.get(f"{record_id}:{event}", False)


def mark_notified(record_id, event: str):
    _store[f"{record_id}:{event}"] = True
    _save()
