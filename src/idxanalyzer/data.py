"""Pengambilan data harga & fundamental.

Sumber utama: Yahoo Finance via `yfinance` (kode saham BEI berakhiran .JK).
Mode demo menghasilkan data sintetis agar pipeline & dashboard bisa diuji tanpa internet.
"""
from __future__ import annotations

import logging
import math
import time
import zlib
from typing import Any

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

OHLCV = ["Open", "High", "Low", "Close", "Volume"]


def yf_symbol(ticker: str) -> str:
    return ticker if ticker.startswith("^") or ticker.endswith(".JK") else f"{ticker}.JK"


def _num(x: Any) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _row(df: pd.DataFrame | None, *names: str) -> pd.Series | None:
    if df is None or df.empty:
        return None
    for n in names:
        if n in df.index:
            s = pd.to_numeric(df.loc[n], errors="coerce").dropna()
            if not s.empty:
                return s.sort_index(ascending=False)  # terbaru dulu
    return None


def _growth(s: pd.Series | None) -> float | None:
    if s is None or len(s) < 2 or not s.iloc[1]:
        return None
    return float(s.iloc[0] / abs(s.iloc[1]) - 1) if s.iloc[1] > 0 else None


# ---------------------------------------------------------------- yfinance
class YahooSource:
    def __init__(self, retries: int = 3, delay: float = 1.0):
        import yfinance  # import di sini agar mode demo tidak butuh yfinance

        self.yf = yfinance
        self.retries = retries
        self.delay = delay

    def _retry(self, fn, what: str):
        for i in range(self.retries):
            try:
                return fn()
            except Exception as e:  # noqa: BLE001 — yfinance melempar berbagai jenis error
                wait = self.delay * (2**i)
                log.warning("%s gagal (%s), coba lagi dalam %.0fs", what, e, wait)
                time.sleep(wait)
        return None

    def prices(self, ticker: str, period: str = "2y") -> pd.DataFrame | None:
        sym = yf_symbol(ticker)
        df = self._retry(lambda: self.yf.Ticker(sym).history(period=period, auto_adjust=True), f"harga {sym}")
        if df is None or df.empty:
            return None
        df = df[[c for c in OHLCV if c in df.columns]].dropna(subset=["Close"])
        df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
        # buang hari tanpa transaksi (volume 0 & harga datar) yang kadang muncul di data Yahoo
        return df[df["Volume"] > 0]

    def fundamentals(self, ticker: str) -> dict[str, Any]:
        sym = yf_symbol(ticker)
        t = self.yf.Ticker(sym)
        info = self._retry(lambda: t.info, f"info {sym}") or {}
        inc = self._retry(lambda: t.income_stmt, f"laba rugi {sym}")
        bal = self._retry(lambda: t.balance_sheet, f"neraca {sym}")
        cf = self._retry(lambda: t.cashflow, f"arus kas {sym}")
        divs = self._retry(lambda: t.dividends, f"dividen {sym}")
        return normalize_yahoo(info, inc, bal, cf, divs)


def normalize_yahoo(info: dict, inc=None, bal=None, cf=None, divs=None) -> dict[str, Any]:
    """Ubah output yfinance menjadi dict metrik standar (rasio desimal)."""
    price = _num(info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose"))
    m: dict[str, Any] = {
        "name": info.get("longName") or info.get("shortName"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "market_cap": _num(info.get("marketCap")),
        "price": price,
        "per": _num(info.get("trailingPE")),
        "pbv": _num(info.get("priceToBook")),
        "roe": _num(info.get("returnOnEquity")),
        "roa": _num(info.get("returnOnAssets")),
        "net_margin": _num(info.get("profitMargins")),
        "revenue_growth": _num(info.get("revenueGrowth")),
        "earnings_growth": _num(info.get("earningsGrowth")),
        "current_ratio": _num(info.get("currentRatio")),
        "eps": _num(info.get("trailingEps")),
        "bvps": _num(info.get("bookValue")),
    }
    de = _num(info.get("debtToEquity"))
    m["debt_to_equity"] = de / 100 if de is not None else None  # Yahoo memberi dalam persen

    # Dividend yield dihitung dari histori dividen 12 bulan (format field Yahoo berubah-ubah).
    m["dividend_yield"] = None
    if divs is not None and len(divs) and price:
        d = divs.copy()
        d.index = pd.to_datetime(d.index).tz_localize(None)
        last12 = d[d.index >= d.index.max() - pd.Timedelta(days=365)]
        if pd.Timestamp.now() - d.index.max() < pd.Timedelta(days=550):
            m["dividend_yield"] = float(last12.sum()) / price

    # Fallback dari laporan keuangan tahunan
    rev, ni = _row(inc, "Total Revenue", "Operating Revenue"), _row(inc, "Net Income", "Net Income Common Stockholders")
    eq = _row(bal, "Stockholders Equity", "Common Stock Equity", "Total Equity Gross Minority Interest")
    ta, debt = _row(bal, "Total Assets"), _row(bal, "Total Debt")
    ocf = _row(cf, "Operating Cash Flow", "Cash Flow From Continuing Operating Activities")

    if m["revenue_growth"] is None:
        m["revenue_growth"] = _growth(rev)
    if m["earnings_growth"] is None:
        m["earnings_growth"] = _growth(ni)
    if m["roe"] is None and ni is not None and eq is not None and eq.iloc[0] > 0:
        m["roe"] = float(ni.iloc[0] / eq.iloc[0])
    if m["roa"] is None and ni is not None and ta is not None and ta.iloc[0] > 0:
        m["roa"] = float(ni.iloc[0] / ta.iloc[0])
    if m["net_margin"] is None and ni is not None and rev is not None and rev.iloc[0] > 0:
        m["net_margin"] = float(ni.iloc[0] / rev.iloc[0])
    if m["debt_to_equity"] is None and debt is not None and eq is not None and eq.iloc[0] > 0:
        m["debt_to_equity"] = float(debt.iloc[0] / eq.iloc[0])

    ocf_v = _num(info.get("operatingCashflow")) or (float(ocf.iloc[0]) if ocf is not None else None)
    ni_v = _num(info.get("netIncomeToCommon")) or (float(ni.iloc[0]) if ni is not None else None)
    m["cash_conversion"] = ocf_v / ni_v if ocf_v is not None and ni_v and ni_v > 0 else None
    return m


# ---------------------------------------------------------------- demo
class DemoSource:
    """Data sintetis deterministik (per ticker) untuk uji coba offline."""

    SECTORS = [
        ("Financial Services", "Banks - Regional"),
        ("Communication Services", "Telecom Services"),
        ("Consumer Defensive", "Packaged Foods"),
        ("Energy", "Thermal Coal"),
        ("Basic Materials", "Other Industrial Metals & Mining"),
        ("Real Estate", "Real Estate - Development"),
        ("Industrials", "Conglomerates"),
    ]

    def __init__(self, bank_tickers: set[str] | None = None):
        self.bank_tickers = bank_tickers or set()

    def _rng(self, ticker: str) -> np.random.Generator:
        return np.random.default_rng(zlib.crc32(ticker.encode()))

    def prices(self, ticker: str, period: str = "2y") -> pd.DataFrame:
        rng = self._rng(ticker)
        n = 500
        idx = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=n)
        start = float(rng.choice([150, 450, 1200, 3000, 6500, 9000]))
        drift = rng.normal(0.0003, 0.0008)
        vol = rng.uniform(0.012, 0.03)
        close = start * np.exp(np.cumsum(rng.normal(drift, vol, n)))
        openp = close * (1 + rng.normal(0, vol / 3, n))
        high = np.maximum(openp, close) * (1 + np.abs(rng.normal(0, vol / 2, n)))
        low = np.minimum(openp, close) * (1 - np.abs(rng.normal(0, vol / 2, n)))
        volume = rng.lognormal(mean=np.log(2e7), sigma=0.5, size=n).round()
        return pd.DataFrame({"Open": openp, "High": high, "Low": low, "Close": close, "Volume": volume}, index=idx)

    def fundamentals(self, ticker: str) -> dict[str, Any]:
        rng = self._rng(ticker + "_f")
        if ticker in self.bank_tickers:
            sector, industry = self.SECTORS[0]
        else:
            sector, industry = self.SECTORS[1 + int(rng.integers(0, len(self.SECTORS) - 1))]
        price = float(self.prices(ticker)["Close"].iloc[-1])
        eps = price / rng.uniform(5, 35)
        bvps = price / rng.uniform(0.6, 4.5)
        return {
            "name": f"PT {ticker} Tbk (demo)",
            "sector": sector,
            "industry": industry,
            "market_cap": price * rng.uniform(1e9, 1.2e11),
            "price": price,
            "per": price / eps,
            "pbv": price / bvps,
            "dividend_yield": rng.uniform(0, 0.08),
            "roe": eps / bvps,
            "roa": rng.uniform(0.01, 0.03) if ticker in self.bank_tickers else rng.uniform(-0.02, 0.15),
            "net_margin": rng.uniform(-0.05, 0.35),
            "revenue_growth": rng.normal(0.06, 0.12),
            "earnings_growth": rng.normal(0.08, 0.2),
            "debt_to_equity": rng.uniform(0.1, 2.5),
            "current_ratio": rng.uniform(0.7, 3.0),
            "cash_conversion": rng.uniform(-0.2, 1.8),
            "eps": eps,
            "bvps": bvps,
        }
