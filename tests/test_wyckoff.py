"""威科夫：特征提取断言（mock 数据）+ LLM 调用 mock。"""
from unittest.mock import patch

import numpy as np
import pandas as pd

from astock.analysis import wyckoff


def _daily(n=130, seed=7):
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0, 1, n))
    vol = rng.integers(80, 120, n).astype(float)
    vol[60] = 500          # 制造一次异常放量
    close[60] = close[59] * 0.94   # 当日暴跌 → SC 候选
    return pd.DataFrame({"date": pd.date_range("2026-01-01", periods=n).astype(str),
                         "open": close, "high": close * 1.01, "low": close * 0.99,
                         "close": close, "volume": vol})


def test_extract_features():
    f = wyckoff.extract_features(_daily())
    assert f["box_high"] > f["box_low"]
    assert 0 <= f["pos_pct"] <= 100
    assert any("SC" in e for e in f["events"])   # 暴跌放量日被捕捉


def test_analyze_llm_mocked():
    with patch.object(wyckoff, "judge_with_llm",
                      return_value="【判定】阶段：吸筹C（置信度：中）\n\n证据…"):
        md, summary = wyckoff.analyze("600519.SH", _daily())
    assert "吸筹C" in summary
    assert "客观特征依据" in md


def test_analyze_llm_failed_degrades():
    with patch.object(wyckoff, "judge_with_llm", side_effect=TimeoutError("slow")):
        md, summary = wyckoff.analyze("600519.SH", _daily())
    assert "LLM 判定失败" in md
    assert summary == "威科夫判定失败"
