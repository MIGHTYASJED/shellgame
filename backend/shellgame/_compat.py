"""Single import point for the data layer (db + tools) used by agents/api/memory."""
from __future__ import annotations

from . import db, tools  # noqa: F401


def main_graph():
    """FalkorDB Graph handle for the main `shellgame` graph."""
    return db.get_graph()
