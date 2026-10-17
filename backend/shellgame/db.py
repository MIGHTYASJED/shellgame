"""FalkorDB connection: FALKORDB_URL -> server client, else embedded falkordblite file."""
from __future__ import annotations

import os
import threading
from pathlib import Path

from .schema import MAIN_GRAPH

_DB = None
_LOCK = threading.Lock()
DEFAULT_LITE_PATH = str(Path(__file__).resolve().parent.parent / ".data" / "shellgame.db")


def lite_path() -> str:
    return os.environ.get("FALKORDB_LITE_PATH") or DEFAULT_LITE_PATH


def get_db():
    """Process-wide FalkorDB handle (server if FALKORDB_URL is set, else embedded falkordblite)."""
    global _DB
    if _DB is None:
        with _LOCK:
            if _DB is None:
                url = os.environ.get("FALKORDB_URL")
                if url:
                    from falkordb import FalkorDB
                    _DB = FalkorDB.from_url(url)
                else:
                    from redislite.falkordb_client import FalkorDB
                    path = lite_path()
                    Path(path).parent.mkdir(parents=True, exist_ok=True)
                    _DB = FalkorDB(path)
    return _DB


def get_graph(name: str = MAIN_GRAPH):
    return get_db().select_graph(name)


def reset_db() -> None:
    """Drop the cached handle (tests switch FALKORDB_LITE_PATH)."""
    global _DB
    _DB = None
