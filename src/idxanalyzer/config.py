"""Memuat konfigurasi YAML."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "config" / "settings.yaml"


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    with open(path or DEFAULT_CONFIG, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    cfg["watchlist"] = [t.strip().upper().removesuffix(".JK") for t in cfg.get("watchlist", [])]
    cfg["bank_tickers"] = {t.upper() for t in cfg.get("bank_tickers", [])}
    return cfg
