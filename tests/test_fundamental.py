import json

import pytest

from idxanalyzer.config import load_config
from idxanalyzer.data import DemoSource, normalize_yahoo
from idxanalyzer.fundamental import fair_value, graham_number, linear_score, score_fundamental, sector_median_per
from idxanalyzer.pipeline import combine, quadrant, run

CFG = load_config()

GOOD = dict(per=8, pbv=0.9, dividend_yield=0.07, roe=0.25, roa=0.12, net_margin=0.25, revenue_growth=0.2,
            earnings_growth=0.25, debt_to_equity=0.3, current_ratio=2.5, cash_conversion=1.2)
BAD = dict(per=-5, pbv=6, dividend_yield=0, roe=-0.1, roa=-0.05, net_margin=-0.1, revenue_growth=-0.2,
           earnings_growth=-0.5, debt_to_equity=3, current_ratio=0.5, cash_conversion=-1)


def test_linear_score_direction():
    assert linear_score(10, full=10, zero=30) == 1
    assert linear_score(30, full=10, zero=30) == 0
    assert linear_score(20, full=10, zero=30) == pytest.approx(0.5)
    assert linear_score(0.25, full=0.2, zero=0) == 1  # dibatasi 1


def test_good_vs_bad_company():
    assert score_fundamental("AAAA", GOOD, CFG)["score"] == 100
    assert score_fundamental("BBBB", BAD, CFG)["score"] == 0


def test_bank_skips_leverage_metrics():
    r = score_fundamental("BBCA", {**GOOD, "debt_to_equity": 8, "roa": 0.025}, CFG)
    assert r["is_bank"]
    assert r["detail"]["debt_to_equity"]["score"] is None
    assert r["detail"]["roa"]["score"] == r["detail"]["roa"]["max"]  # ambang bank 2%
    assert r["score"] == 100


def test_missing_data_renormalizes():
    r = score_fundamental("CCCC", {"roe": 0.2, "per": 10}, CFG)
    assert r["score"] == 100
    assert 0 < r["coverage"] < 0.3


def test_graham_and_fair_value():
    assert graham_number(100, 1000) == pytest.approx((22.5 * 100 * 1000) ** 0.5)
    assert graham_number(-1, 1000) is None
    med = sector_median_per([{"per": 10, "sector": "X"}, {"per": 20, "sector": "X"}, {"per": 500, "sector": "X"}])
    assert med == {"X": 15}
    fv = fair_value({"eps": 100, "bvps": 1000, "sector": "X"}, 1000, med)
    assert fv["relative_per"] == 1500 and fv["fair_value"] > 1000 and fv["margin_of_safety"] > 0


def test_quadrant_and_combine():
    assert quadrant(70, 60, CFG) == "Kandidat utama"
    assert quadrant(70, 40, CFG) == "Value, tunggu momentum"
    assert quadrant(40, 70, CFG) == "Momentum spekulatif"
    assert quadrant(40, 40, CFG) == "Hindari"
    assert combine(80, 50, CFG) == pytest.approx(68.0)
    assert combine(None, 50, CFG) == 50


def test_normalize_yahoo_units():
    m = normalize_yahoo({"trailingPE": 12.5, "debtToEquity": 45.0, "returnOnEquity": 0.18, "currentPrice": 1000})
    assert m["per"] == 12.5 and m["debt_to_equity"] == pytest.approx(0.45) and m["roe"] == 0.18


def test_pipeline_demo_end_to_end(tmp_path):
    rows = run(DemoSource(CFG["bank_tickers"]), CFG, ["BBCA", "TLKM", "ASII"], tmp_path, mode="demo")
    assert len(rows) == 3
    data = json.loads((tmp_path / "data" / "latest.json").read_text())
    assert data["count"] == 3 and data["mode"] == "demo"
    assert (tmp_path / "data" / "prices" / "BBCA.json").exists()
    assert (tmp_path / "index.html").exists()
    assert (tmp_path / "data" / "summary.csv").exists()
