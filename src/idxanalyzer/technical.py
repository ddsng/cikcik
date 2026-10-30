"""Indikator dan skor teknikal (lihat docs/KONSEP_ANALISA.md bagian 2).

Semua indikator dihitung dengan pandas murni agar tidak bergantung pada TA-Lib.
Input: DataFrame berindeks tanggal dengan kolom Open, High, Low, Close, Volume.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd


# ---------------------------------------------------------------- indikator
def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=n).mean()


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False, min_periods=n).mean()


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    rs = gain / loss.replace(0, np.nan)
    out = 100 - 100 / (1 + rs)
    # loss == 0 → RSI 100 (hanya naik)
    return out.where(loss != 0, 100.0)


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    line = ema(close, fast) - ema(close, slow)
    sig = line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    return pd.DataFrame({"macd": line, "signal": sig, "hist": line - sig})


def bollinger(close: pd.Series, n: int = 20, k: float = 2.0) -> pd.DataFrame:
    mid = sma(close, n)
    sd = close.rolling(n, min_periods=n).std(ddof=0)
    upper, lower = mid + k * sd, mid - k * sd
    pct_b = (close - lower) / (upper - lower).replace(0, np.nan)
    return pd.DataFrame({"mid": mid, "upper": upper, "lower": lower, "pct_b": pct_b})


def true_range(df: pd.DataFrame) -> pd.Series:
    prev = df["Close"].shift()
    return pd.concat(
        [df["High"] - df["Low"], (df["High"] - prev).abs(), (df["Low"] - prev).abs()], axis=1
    ).max(axis=1)


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    return true_range(df).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def adx(df: pd.DataFrame, n: int = 14) -> pd.DataFrame:
    up = df["High"].diff()
    down = -df["Low"].diff()
    plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=df.index)
    minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=df.index)
    tr = true_range(df).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    plus_di = 100 * plus_dm.ewm(alpha=1 / n, adjust=False, min_periods=n).mean() / tr
    minus_di = 100 * minus_dm.ewm(alpha=1 / n, adjust=False, min_periods=n).mean() / tr
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return pd.DataFrame(
        {"adx": dx.ewm(alpha=1 / n, adjust=False, min_periods=n).mean(), "plus_di": plus_di, "minus_di": minus_di}
    )


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Kembalikan salinan df dengan semua kolom indikator."""
    out = df.copy()
    c = out["Close"]
    for n in (20, 50, 200):
        out[f"sma{n}"] = sma(c, n)
    out["rsi14"] = rsi(c)
    out = out.join(macd(c))
    bb = bollinger(c)
    out["bb_upper"], out["bb_lower"], out["pct_b"] = bb["upper"], bb["lower"], bb["pct_b"]
    out["atr14"] = atr(out)
    out = out.join(adx(out))
    out["vol_ratio"] = sma(out["Volume"], 5) / sma(out["Volume"], 20).replace(0, np.nan)
    out["value"] = c * out["Volume"]
    return out


# ---------------------------------------------------------------- utilitas BEI
def idx_tick(price: float) -> int:
    """Fraksi harga BEI."""
    if price < 200:
        return 1
    if price < 500:
        return 2
    if price < 2000:
        return 5
    if price < 5000:
        return 10
    return 25


def round_tick(price: float, mode: str = "nearest") -> float:
    if price is None or not math.isfinite(price) or price <= 0:
        return float("nan")
    t = idx_tick(price)
    f = {"down": math.floor, "up": math.ceil}.get(mode, round)
    return float(max(t, f(price / t) * t))


def label_technical(score: float) -> str:
    if score >= 70:
        return "Bullish kuat"
    if score >= 55:
        return "Bullish"
    if score >= 45:
        return "Netral"
    if score >= 30:
        return "Bearish"
    return "Bearish kuat"


def _f(x: Any) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


# ---------------------------------------------------------------- skor
def score_technical(df: pd.DataFrame, risk_cfg: dict | None = None) -> dict[str, Any]:
    """Hitung skor teknikal 0–100 beserta rincian & level risiko.

    Membutuhkan minimal ~60 bar; komponen yang butuh SMA200 bernilai 0 jika histori kurang.
    """
    risk_cfg = risk_cfg or {}
    if df is None or len(df) < 60:
        return {"score": None, "label": "Data kurang", "reasons": ["Histori < 60 hari"]}

    d = add_indicators(df)
    last, close = d.iloc[-1], float(d["Close"].iloc[-1])
    reasons: list[str] = []
    comp = {"trend": 0.0, "momentum": 0.0, "adx": 0.0, "position": 0.0, "volume": 0.0}

    # Tren (30)
    s20, s50, s200 = _f(last["sma20"]), _f(last["sma50"]), _f(last["sma200"])
    if s20 and close > s20:
        comp["trend"] += 5
    if s50 and close > s50:
        comp["trend"] += 10
        reasons.append("Harga di atas SMA50")
    if s50 and s200 and s50 > s200:
        comp["trend"] += 10
        reasons.append("SMA50 > SMA200 (tren naik jangka menengah)")
    elif s50 and s200:
        reasons.append("SMA50 < SMA200 (tren turun jangka menengah)")
    if len(d) > 220:
        prev200 = _f(d["sma200"].iloc[-21])
        if s200 and prev200 and s200 > prev200:
            comp["trend"] += 5

    # Momentum (25)
    r = _f(last["rsi14"])
    if r is not None:
        if 50 <= r <= 70:
            comp["momentum"] += 15
        elif 40 <= r < 50:
            comp["momentum"] += 10
        elif 30 <= r < 40:
            comp["momentum"] += 6
        elif r < 30:
            comp["momentum"] += 8
            reasons.append(f"RSI {r:.0f}: jenuh jual, potensi pantulan")
        else:
            comp["momentum"] += 5
            reasons.append(f"RSI {r:.0f}: jenuh beli")
    h = _f(last["hist"])
    if h is not None and h > 0:
        comp["momentum"] += 10
        prev_h = _f(d["hist"].iloc[-2])
        if prev_h is not None and prev_h <= 0:
            reasons.append("MACD baru golden cross")

    # ADX (15)
    a, pdi, mdi = _f(last["adx"]), _f(last["plus_di"]), _f(last["minus_di"])
    if a is not None and pdi is not None and mdi is not None:
        if a >= 25 and pdi > mdi:
            comp["adx"] = 15
            reasons.append(f"ADX {a:.0f}: tren naik kuat")
        elif a >= 25:
            comp["adx"] = 0
            reasons.append(f"ADX {a:.0f}: tren turun kuat")
        elif a < 20:
            comp["adx"] = 7
        else:
            comp["adx"] = 10

    # Posisi harga (15)
    pb = _f(last["pct_b"])
    if pb is not None:
        comp["position"] += 10 if 0.2 <= pb <= 0.8 else (7 if pb < 0.2 else 4)
    win = d.tail(250)
    hi52, lo52 = float(win["High"].max()), float(win["Low"].min())
    dist_hi = (hi52 - close) / hi52 if hi52 else None
    if dist_hi is not None and dist_hi <= 0.15:
        comp["position"] += 5
        reasons.append("Dekat high 52 minggu")

    # Volume (15)
    vr = _f(last["vol_ratio"])
    chg5 = close / float(d["Close"].iloc[-6]) - 1 if len(d) > 6 else 0.0
    if vr is not None:
        if vr > 1.2 and chg5 > 0:
            comp["volume"] = 15
            reasons.append(f"Volume naik {vr:.1f}× disertai kenaikan harga (akumulasi)")
        elif vr > 1.2 and chg5 < 0:
            comp["volume"] = 0
            reasons.append("Volume naik saat harga turun (distribusi)")
        elif vr > 1.0:
            comp["volume"] = 10
        else:
            comp["volume"] = 5

    score = round(sum(comp.values()), 1)

    # Risiko & level
    at = _f(last["atr14"]) or 0.0
    stop = round_tick(close - risk_cfg.get("atr_stop_mult", 2.0) * at, "down")
    target = round_tick(close + risk_cfg.get("atr_target_mult", 3.0) * at, "up")
    recent = d.tail(20)
    prev_bar = d.iloc[-2]
    pivot = (prev_bar["High"] + prev_bar["Low"] + prev_bar["Close"]) / 3
    avg_value = _f(d["value"].tail(20).mean())

    return {
        "score": score,
        "label": label_technical(score),
        "components": comp,
        "reasons": reasons,
        "close": close,
        "change_1d": _f(close / float(d["Close"].iloc[-2]) - 1),
        "change_5d": _f(chg5),
        "change_20d": _f(close / float(d["Close"].iloc[-21]) - 1) if len(d) > 21 else None,
        "rsi": r,
        "macd_hist": h,
        "adx": a,
        "pct_b": pb,
        "vol_ratio": vr,
        "sma20": s20,
        "sma50": s50,
        "sma200": s200,
        "atr": at,
        "high_52w": hi52,
        "low_52w": lo52,
        "support": round_tick(float(recent["Low"].min())),
        "resistance": round_tick(float(recent["High"].max())),
        "pivot": round_tick(float(pivot)),
        "stop_loss": stop,
        "target": target,
        "avg_value_20d": avg_value,
        "as_of": str(d.index[-1].date()) if hasattr(d.index[-1], "date") else str(d.index[-1]),
    }
