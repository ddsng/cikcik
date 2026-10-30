import numpy as np
import pandas as pd
import pytest

from idxanalyzer.technical import idx_tick, round_tick, rsi, score_technical, sma


def make_df(closes, vol=1_000_000):
    closes = np.asarray(closes, dtype=float)
    idx = pd.bdate_range("2024-01-01", periods=len(closes))
    return pd.DataFrame({
        "Open": closes, "High": closes * 1.01, "Low": closes * 0.99,
        "Close": closes, "Volume": np.full(len(closes), vol, dtype=float)}, index=idx)


def test_sma_basic():
    s = pd.Series([1, 2, 3, 4, 5], dtype=float)
    assert sma(s, 3).tolist()[2:] == [2.0, 3.0, 4.0]


def test_rsi_bounds_and_extremes():
    up = pd.Series(np.arange(1, 60, dtype=float))
    assert rsi(up).iloc[-1] == pytest.approx(100.0)
    down = pd.Series(np.arange(60, 1, -1, dtype=float))
    assert rsi(down).iloc[-1] < 5
    rnd = pd.Series(100 + np.random.default_rng(1).normal(0, 1, 300).cumsum())
    r = rsi(rnd).dropna()
    assert ((r >= 0) & (r <= 100)).all()


@pytest.mark.parametrize("price,tick", [(50, 1), (199, 1), (200, 2), (499, 2), (500, 5), (1999, 5),
                                        (2000, 10), (4990, 10), (5000, 25), (9875, 25)])
def test_idx_tick(price, tick):
    assert idx_tick(price) == tick


def test_round_tick():
    assert round_tick(1237, "down") == 1235
    assert round_tick(1237, "up") == 1240
    assert round_tick(6012) == 6000
    assert round_tick(-5) != round_tick(-5)  # NaN


def test_uptrend_scores_higher_than_downtrend():
    n = 300
    rng = np.random.default_rng(0)
    up = 1000 * np.exp(np.cumsum(0.003 + rng.normal(0, 0.008, n)))
    down = 1000 * np.exp(np.cumsum(-0.003 + rng.normal(0, 0.008, n)))
    s_up, s_down = score_technical(make_df(up)), score_technical(make_df(down))
    assert s_up["score"] > s_down["score"]
    assert s_up["label"].startswith("Bullish")
    assert 0 <= s_down["score"] <= 100
    # stop loss di bawah harga, target di atas
    assert s_up["stop_loss"] < s_up["close"] < s_up["target"]


def test_short_history_returns_none():
    assert score_technical(make_df(np.linspace(100, 110, 30)))["score"] is None
