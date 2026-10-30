"""Command-line interface.

Contoh:
    python -m idxanalyzer run                 # semua watchlist, data live yfinance
    python -m idxanalyzer run --demo          # data sintetis (tanpa internet)
    python -m idxanalyzer run -t BBCA,TLKM    # ticker tertentu
    python -m idxanalyzer show BBCA           # rincian satu saham (live)
"""
from __future__ import annotations

import argparse
import json
import logging
import sys

from .config import load_config
from .pipeline import analyze_ticker, run


def _source(args, cfg):
    if args.demo:
        from .data import DemoSource
        return DemoSource(cfg["bank_tickers"])
    from .data import YahooSource
    return YahooSource(delay=cfg.get("request_delay_sec", 1.0))


def _fmt(v, pct=False):
    if v is None:
        return "-"
    return f"{v * 100:.1f}%" if pct else (f"{v:,.2f}" if abs(v) < 1000 else f"{v:,.0f}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="idxanalyzer", description="Analisa teknikal & fundamental saham BEI")
    p.add_argument("--config", help="path settings.yaml")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="analisa seluruh watchlist & tulis output dashboard")
    r.add_argument("-t", "--tickers", help="daftar ticker dipisah koma (default: watchlist)")
    r.add_argument("-o", "--out", default="site", help="folder output (default: site)")
    r.add_argument("--demo", action="store_true", help="pakai data sintetis")

    s = sub.add_parser("show", help="tampilkan analisa satu saham")
    s.add_argument("ticker")
    s.add_argument("--demo", action="store_true")
    s.add_argument("--json", action="store_true")

    args = p.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    cfg = load_config(args.config)
    src = _source(args, cfg)

    if args.cmd == "run":
        tickers = [t.strip().upper() for t in args.tickers.split(",")] if args.tickers else None
        rows = run(src, cfg, tickers, args.out, mode="demo" if args.demo else "live")
        print(f"\n{'Ticker':<7}{'Skor':>6}{'F':>6}{'T':>6}  Kuadran")
        for x in rows[:15]:
            print(f"{x['ticker']:<7}{_fmt(x['final_score']):>6}{_fmt(x['fundamental']['score']):>6}"
                  f"{_fmt(x['technical']['score']):>6}  {x['quadrant']}")
        print(f"\n{len(rows)} saham dianalisa → {args.out}/data/latest.json")
        return 0 if rows else 1

    tk = args.ticker.upper().removesuffix(".JK")
    x = analyze_ticker(tk, src, cfg)
    x.pop("_prices", None)
    if args.json:
        print(json.dumps(x, indent=2, default=str, ensure_ascii=False))
        return 0
    t, f = x["technical"], x["fundamental"]
    print(f"\n{tk} — {x['name'] or ''} ({x['sector'] or '-'})")
    print(f"Harga {_fmt(t.get('close'))} | Teknikal {_fmt(t.get('score'))} ({t.get('label')}) | "
          f"Fundamental {_fmt(f['score'])} (coverage {f['coverage']:.0%})")
    print(f"RSI {_fmt(t.get('rsi'))} | SL {_fmt(t.get('stop_loss'))} | Target {_fmt(t.get('target'))} | "
          f"Support {_fmt(t.get('support'))} | Resistance {_fmt(t.get('resistance'))}")
    m = x["metrics"]
    print(f"PER {_fmt(m['per'])} | PBV {_fmt(m['pbv'])} | ROE {_fmt(m['roe'], True)} | "
          f"DER {_fmt(m['debt_to_equity'])} | Yield {_fmt(m['dividend_yield'], True)}")
    print("Catatan:", "; ".join(t.get("reasons", []) + f["reasons"]) or "-")
    return 0


if __name__ == "__main__":
    sys.exit(main())
