"""Orkestrasi: ambil data → analisa → skor gabungan → tulis output."""
from __future__ import annotations

import json
import logging
import math
import shutil
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from .fundamental import fair_value, score_fundamental, sector_median_per
from .technical import add_indicators, score_technical

log = logging.getLogger(__name__)
WIB = timezone(timedelta(hours=7))


def quadrant(f: float | None, t: float | None, cfg: dict) -> str:
    if f is None or t is None:
        return "Data tidak lengkap"
    q = cfg.get("quadrant", {})
    good_f = f >= q.get("fundamental_threshold", 60)
    good_t = t >= q.get("technical_threshold", 55)
    if good_f and good_t:
        return "Kandidat utama"
    if good_f:
        return "Value, tunggu momentum"
    if good_t:
        return "Momentum spekulatif"
    return "Hindari"


def combine(f: float | None, t: float | None, cfg: dict) -> float | None:
    w = cfg.get("weights", {"fundamental": 0.6, "technical": 0.4})
    if f is None and t is None:
        return None
    if f is None:
        return t
    if t is None:
        return f
    return round(w["fundamental"] * f + w["technical"] * t, 1)


def analyze_ticker(ticker: str, source, cfg: dict) -> dict[str, Any]:
    prices = source.prices(ticker, cfg.get("history_period", "2y"))
    tech = score_technical(prices, cfg.get("risk"))
    try:
        fund_raw = source.fundamentals(ticker)
    except Exception as e:  # noqa: BLE001
        log.warning("Fundamental %s gagal: %s", ticker, e)
        fund_raw = {}
    fund = score_fundamental(ticker, fund_raw, cfg)
    min_val = cfg.get("liquidity", {}).get("min_avg_value_idr", 0)
    avg_val = tech.get("avg_value_20d")
    return {
        "ticker": ticker,
        "name": fund_raw.get("name"),
        "sector": fund_raw.get("sector"),
        "industry": fund_raw.get("industry"),
        "market_cap": fund_raw.get("market_cap"),
        "metrics": {k: fund_raw.get(k) for k in (
            "per", "pbv", "dividend_yield", "roe", "roa", "net_margin", "revenue_growth",
            "earnings_growth", "debt_to_equity", "current_ratio", "cash_conversion", "eps", "bvps")},
        "technical": tech,
        "fundamental": fund,
        "illiquid": bool(avg_val is not None and avg_val < min_val),
        "_prices": prices,
    }


def _clean(o: Any) -> Any:
    """Ganti NaN/inf dengan None agar JSON valid."""
    if isinstance(o, float):
        return o if math.isfinite(o) else None
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if hasattr(o, "item"):  # numpy scalar
        return _clean(o.item())
    return o


def price_payload(df: pd.DataFrame, bars: int = 250) -> dict[str, Any]:
    d = add_indicators(df).tail(bars)
    return {
        "date": [i.strftime("%Y-%m-%d") for i in d.index],
        **{k.lower(): d[k].round(2).tolist() for k in ("Open", "High", "Low", "Close")},
        "volume": d["Volume"].astype(float).tolist(),
        "sma20": d["sma20"].round(2).tolist(),
        "sma50": d["sma50"].round(2).tolist(),
        "sma200": d["sma200"].round(2).tolist(),
        "rsi": d["rsi14"].round(1).tolist(),
    }


def run(source, cfg: dict, tickers: list[str] | None = None, out_dir: str | Path = "site",
        mode: str = "live") -> list[dict[str, Any]]:
    tickers = tickers or cfg["watchlist"]
    out = Path(out_dir)
    (out / "data" / "prices").mkdir(parents=True, exist_ok=True)
    (out / "data" / "history").mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    for i, tk in enumerate(tickers, 1):
        log.info("[%d/%d] %s", i, len(tickers), tk)
        try:
            r = analyze_ticker(tk, source, cfg)
        except Exception as e:  # noqa: BLE001
            log.error("Gagal menganalisa %s: %s", tk, e)
            continue
        rows.append(r)
        if mode == "live" and i < len(tickers):
            time.sleep(cfg.get("request_delay_sec", 1.0))

    # Nilai wajar butuh median PER sektor dari seluruh universe
    flat = [{"per": r["metrics"]["per"], "sector": r["sector"]} for r in rows]
    sec_per = sector_median_per(flat)
    for r in rows:
        price = r["technical"].get("close")
        r["valuation"] = fair_value({**r["metrics"], "sector": r["sector"]}, price, sec_per)
        f, t = r["fundamental"]["score"], r["technical"]["score"]
        r["final_score"] = combine(f, t, cfg)
        r["quadrant"] = quadrant(f, t, cfg)
        if r["_prices"] is not None and len(r["_prices"]):
            (out / "data" / "prices" / f"{r['ticker']}.json").write_text(
                json.dumps(_clean(price_payload(r["_prices"]))), encoding="utf-8")
        del r["_prices"]

    rows.sort(key=lambda r: (r["final_score"] is None, -(r["final_score"] or 0)))
    now = datetime.now(WIB)
    payload = _clean({
        "generated_at": now.isoformat(timespec="minutes"),
        "mode": mode,
        "weights": cfg.get("weights"),
        "quadrant_thresholds": cfg.get("quadrant"),
        "count": len(rows),
        "stocks": rows,
    })
    (out / "data" / "latest.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "data" / "history" / f"{now:%Y-%m-%d}.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    write_summary_csv(rows, out / "data" / "summary.csv")
    # salin dashboard statis
    web = Path(__file__).resolve().parents[2] / "web"
    if web.is_dir():
        for f in web.iterdir():
            if f.is_file():
                shutil.copy2(f, out / f.name)
    (out / ".nojekyll").touch()
    return rows


def write_summary_csv(rows: list[dict], path: Path) -> None:
    recs = []
    for r in rows:
        t, f, v = r["technical"], r["fundamental"], r.get("valuation", {})
        recs.append({
            "ticker": r["ticker"], "name": r["name"], "sector": r["sector"],
            "final_score": r["final_score"], "quadrant": r["quadrant"],
            "fundamental_score": f["score"], "coverage": f["coverage"],
            "technical_score": t.get("score"), "technical_label": t.get("label"),
            "close": t.get("close"), "stop_loss": t.get("stop_loss"), "target": t.get("target"),
            "fair_value": v.get("fair_value"), "margin_of_safety": v.get("margin_of_safety"),
            **{k: r["metrics"].get(k) for k in ("per", "pbv", "roe", "dividend_yield", "debt_to_equity")},
            "rsi": t.get("rsi"), "illiquid": r["illiquid"],
        })
    pd.DataFrame(recs).to_csv(path, index=False)
