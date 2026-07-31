"""周线/30分钟取数：全 mock，验证降级与列名规范化。"""
from unittest.mock import patch

import pandas as pd

from astock.adapters import market_data

_CN = pd.DataFrame({"日期": ["2026-07-24", "2026-07-31"], "开盘": [1, 2],
                    "收盘": [2, 3], "最高": [3, 4], "最低": [0.5, 1.5],
                    "成交量": [100, 200], "成交额": [1e6, 2e6],
                    "换手率": [0.1, 0.2]})

_SINA_D = pd.DataFrame({"date": pd.date_range("2026-07-20", periods=10).astype(str),
                        "open": range(10), "high": [i + 2 for i in range(10)],
                        "low": [i - 1 for i in range(10)], "close": [i + 1 for i in range(10)],
                        "volume": [100] * 10, "amount": [1e6] * 10})

_SINA_M = pd.DataFrame({"day": ["2026-07-31 10:00:00", "2026-07-31 10:30:00"],
                        "open": ["1.0", "2.0"], "high": ["3.0", "4.0"],
                        "low": ["0.5", "1.5"], "close": ["2.0", "3.0"],
                        "volume": ["100", "200"], "amount": ["1e6", "2e6"]})


def test_weekly_em_ok():
    with patch.object(market_data.ak, "stock_zh_a_hist", return_value=_CN.copy()):
        df = market_data._weekly_df("600519", "2026-01-01", "2026-07-31")
    assert list(df.columns[:5]) == ["date", "open", "close", "high", "low"]
    assert df.attrs["source"] == "东方财富"


def test_weekly_fallback_resample():
    with patch.object(market_data.ak, "stock_zh_a_hist", side_effect=OSError("down")), \
         patch.object(market_data.ak, "stock_zh_a_daily", return_value=_SINA_D.copy()):
        df = market_data._weekly_df("600519", "2026-07-01", "2026-07-31")
    assert df.attrs["source"] == "新浪(日K重采样)"
    assert len(df) < len(_SINA_D)          # 重采样后周数 < 天数
    assert df["high"].notna().all()
    assert (df["volume"] > 0).all()


def test_min30_fallback_sina_numeric():
    with patch.object(market_data.ak, "stock_zh_a_hist_min_em", side_effect=OSError("down")), \
         patch.object(market_data.ak, "stock_zh_a_minute", return_value=_SINA_M.copy()):
        df = market_data._min30_df("600519", "2026-07-31")
    assert df.attrs["source"] == "新浪"
    assert df["close"].dtype.kind == "f"   # 字符串已转数值
    assert list(df["date"]) == ["2026-07-31 10:00:00", "2026-07-31 10:30:00"]
