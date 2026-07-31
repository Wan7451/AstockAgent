"""structure 统筹：build 产出三件套 + 摘要注入 get_stock_data 输出。"""
from unittest.mock import patch

import numpy as np
import pandas as pd

from astock.adapters import market_data
from astock.analysis import structure


def _kline(n):
    rng = np.random.default_rng(3)
    close = 100 + np.cumsum(rng.normal(0, 1, n))
    return pd.DataFrame({"date": pd.date_range("2025-01-01", periods=n).astype(str),
                         "open": close, "high": close * 1.02, "low": close * 0.98,
                         "close": close, "volume": rng.integers(80, 120, n),
                         "amount": [1e6] * n, "turnover": [0.1] * n})


def test_build_and_digest():
    with patch.object(structure.market_data, "_daily_df", return_value=_kline(200)), \
         patch.object(structure.market_data, "_weekly_df", return_value=_kline(100)), \
         patch.object(structure.market_data, "_min30_df", return_value=_kline(300)), \
         patch.object(structure.wyckoff, "judge_with_llm",
                      return_value="【判定】阶段：吸筹C（置信度：中）\n证据…"):
        out = structure.build("600519", "2026-07-31")
    assert "三级别联立结论" in out["chanlun_md"]
    assert "吸筹C" in out["digest"] and "缠论" in out["digest"]
    assert structure.get_digest("600519.SH") == out["digest"]


def test_digest_injected_into_stock_data():
    structure._DIGESTS["600519.SH"] = "缠论：测试摘要。\n威科夫：吸筹C。"
    with patch.object(market_data, "_daily_df", return_value=_kline(30)):
        text = market_data.get_stock_data("600519", "2026-06-01", "2026-07-31")
    assert "结构分析摘要（缠论/威科夫）" in text
    assert "吸筹C" in text
    structure._DIGESTS.clear()


def test_no_digest_no_injection():
    structure._DIGESTS.clear()
    with patch.object(market_data, "_daily_df", return_value=_kline(30)):
        text = market_data.get_stock_data("600519", "2026-06-01", "2026-07-31")
    assert "结构分析摘要" not in text
