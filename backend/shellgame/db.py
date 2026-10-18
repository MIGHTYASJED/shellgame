"""FalkorDB connection: FALKORDB_URL -> server client, else embedded falkordblite file."""
from __future__ import annotations

import logging
import os
import threading
from pathlib import Path

from .schema import MAIN_GRAPH

log = logging.getLogger("shellgame.db")
_DB = None
_LOCK = threading.Lock()
DEFAULT_LITE_PATH = str(Path(__file__).resolve().parent.parent / ".data" / "shellgame.db")


def lite_path() -> str:
    return os.environ.get("FALKORDB_LITE_PATH") or DEFAULT_LITE_PATH


def _connect():
    url = os.environ.get("FALKORDB_URL")
    if url:
        from falkordb import FalkorDB
        return FalkorDB.from_url(url)
    from redislite.falkordb_client import FalkorDB
    path = lite_path()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    return FalkorDB(path)


def _alive(db) -> bool:
    try:
        return bool(db.connection.ping())
    except Exception:
        return False


def get_db():
    """Process-wide FalkorDB handle (server if FALKORDB_URL is set, else embedded falkordblite).
    Self-healing: if the database process has died, reconnect (falkordblite restarts it from the db file)."""
    global _DB
    with _LOCK:
        if _DB is not None and not _alive(_DB):
            log.warning("FalkorDB connection lost; reconnecting")
            _DB = None
        if _DB is None:
            _DB = _connect()
    return _DB


def get_graph(name: str = MAIN_GRAPH):
    return get_db().select_graph(name)


def reset_db() -> None:
    """Drop the cached handle (tests switch FALKORDB_LITE_PATH)."""
    global _DB
    _DB = None
