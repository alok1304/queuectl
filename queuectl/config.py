from __future__ import annotations
from typing import Optional

from .db import init_db, get_config as _get, set_config as _set, all_config as _all

# Public API for config access; ensures DB exists first

def ensure_bootstrapped() -> None:
    init_db()


def get_value(key: str, default: Optional[str] = None) -> Optional[str]:
    ensure_bootstrapped()
    return _get(key, default)


def set_value(key: str, value: str) -> None:
    ensure_bootstrapped()
    _set(key, value)


def get_all() -> dict:
    ensure_bootstrapped()
    return _all()