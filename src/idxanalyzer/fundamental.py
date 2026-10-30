"""Skor fundamental & nilai wajar (lihat docs/KONSEP_ANALISA.md bagian 3).

Input berupa dict metrik ternormalisasi (rasio dalam desimal, mis. ROE 0.18 = 18%):
    per, pbv, dividend_yield, roe, roa, net_margin, revenue_growth, earnings_growth,
    debt_to_equity, current_ratio, cash_conversion, eps, bvps, sector, industry
"""
from __future__ import annotations

import math
import statistics
from typing import Any

PILLARS = {
    "valuasi": ["per", "pbv", "dividend_yield"],
    "profitabilitas": ["roe", "roa", "net_margin"],
    "pertumbuhan": ["revenue_growth", "earnings_growth"],
    "kesehatan": ["debt_to_equity", "current_ratio", "cash_conversion"],
}


def _valid(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def linear_score(value: float, full: float, zero: float) -> float:
    """Skor 0–1: 1 pada `full`, 0 pada `zero`, linier di antaranya (arah otomatis)."""
    if full == zero:
        return 1.0 if value == full else 0.0
    t = (value - zero) / (full - zero)
    return max(0.0, min(1.0, t))


def is_bank(ticker: str, metrics: dict, bank_tickers: set[str] | None = None) -> bool:
    if bank_tickers and ticker.upper() in bank_tickers:
        return True
    ind = (metrics.get("industry") or "").lower()
    return "bank" in ind


def score_fundamental(ticker: str, m: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    fcfg: dict = cfg["fundamental"]
    bank = is_bank(ticker, m, cfg.get("bank_tickers"))
    detail: dict[str, dict] = {}
    got = total = 0.0
    pillar_pts: dict[str, list[float]] = {p: [0.0, 0.0] for p in PILLARS}

    for pillar, keys in PILLARS.items():
        for key in keys:
            rule = fcfg.get(key)
            if not rule:
                continue
            if bank and rule.get("skip_for_bank"):
                detail[key] = {"value": m.get(key), "score": None, "note": "tidak relevan untuk bank"}
                continue
            w = float(rule["weight"])
            total += w
            v = m.get(key)
            if not _valid(v):
                detail[key] = {"value": None, "score": None, "note": "data tidak tersedia"}
                continue
            full = rule.get("bank_full", rule["full"]) if bank else rule["full"]
            # PER negatif (rugi) = skor 0
            s = 0.0 if key == "per" and v <= 0 else linear_score(float(v), full, rule["zero"])
            detail[key] = {"value": v, "score": round(s * w, 2), "max": w}
            got += w
            pillar_pts[pillar][0] += s * w
            pillar_pts[pillar][1] += w

    coverage = got / total if total else 0.0
    raw = sum(p[0] for p in pillar_pts.values())
    score = round(100 * raw / got, 1) if got else None

    reasons = []
    for key, txt_good, txt_bad in [
        ("roe", "ROE tinggi", "ROE rendah"),
        ("per", "Valuasi PER murah", "PER mahal / rugi"),
        ("earnings_growth", "Laba tumbuh", "Laba turun"),
        ("debt_to_equity", "Utang rendah", "Utang tinggi"),
        ("dividend_yield", "Dividen menarik", None),
    ]:
        d = detail.get(key, {})
        if d.get("score") is None:
            continue
        ratio = d["score"] / d["max"]
        if ratio >= 0.8:
            reasons.append(txt_good)
        elif ratio <= 0.2 and txt_bad:
            reasons.append(txt_bad)

    return {
        "score": score,
        "coverage": round(coverage, 2),
        "is_bank": bank,
        "pillars": {p: (round(100 * a / b, 1) if b else None) for p, (a, b) in pillar_pts.items()},
        "detail": detail,
        "reasons": reasons,
    }


def graham_number(eps: float | None, bvps: float | None) -> float | None:
    if _valid(eps) and _valid(bvps) and eps > 0 and bvps > 0:
        return math.sqrt(22.5 * eps * bvps)
    return None


def sector_median_per(rows: list[dict[str, Any]]) -> dict[str, float]:
    """Median PER positif (< 100×) per sektor dari seluruh universe."""
    bucket: dict[str, list[float]] = {}
    for r in rows:
        per, sector = r.get("per"), r.get("sector") or "Lainnya"
        if _valid(per) and 0 < per < 100:
            bucket.setdefault(sector, []).append(per)
    return {s: statistics.median(v) for s, v in bucket.items() if len(v) >= 2}


def fair_value(m: dict[str, Any], price: float | None, sector_per: dict[str, float]) -> dict[str, Any]:
    g = graham_number(m.get("eps"), m.get("bvps"))
    med = sector_per.get(m.get("sector") or "Lainnya")
    rel = m["eps"] * med if med and _valid(m.get("eps")) and m["eps"] > 0 else None
    vals = [v for v in (g, rel) if v]
    fv = sum(vals) / len(vals) if vals else None
    mos = (fv - price) / fv if fv and _valid(price) else None
    return {
        "graham": round(g, 0) if g else None,
        "relative_per": round(rel, 0) if rel else None,
        "sector_median_per": round(med, 1) if med else None,
        "fair_value": round(fv, 0) if fv else None,
        "margin_of_safety": round(mos, 3) if mos is not None else None,
    }
