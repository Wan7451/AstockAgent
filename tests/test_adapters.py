from unittest.mock import patch

import pandas as pd
import pytest

from astock.adapters import market_data

_FAKE = pd.DataFrame({
    "日期": pd.date_range("2026-06-01", periods=80).strftime("%Y-%m-%d"),
    "开盘": [10.0 + i * 0.1 for i in range(80)],
    "收盘": [10.1 + i * 0.1 for i in range(80)],
    "最高": [10.2 + i * 0.1 for i in range(80)],
    "最低": [9.9 + i * 0.1 for i in range(80)],
    "成交量": [100 + i for i in range(80)],
    "成交额": [1000.0 + i for i in range(80)],
    "换手率": [1.0] * 80,
})


@patch("astock.adapters.market_data.ak.stock_zh_a_hist", return_value=_FAKE)
def test_get_stock_data_format(mock_hist):
    out = market_data.get_stock_data("600519", "2026-06-01", "2026-08-19")
    assert "600519.SH" in out
    assert "date,open,close,high,low,volume" in out.replace(" ", "")
    mock_hist.assert_called_once()
    assert mock_hist.call_args.kwargs["symbol"] == "600519"
    assert mock_hist.call_args.kwargs["adjust"] == "qfq"


@patch("astock.adapters.market_data.ak.stock_zh_a_hist", return_value=_FAKE)
def test_get_indicators_sma(mock_hist):
    out = market_data.get_indicators("000001", "close_10_sma", "2026-08-19", 5)
    assert "000001.SZ" in out and "close_10_sma" in out
    # 末尾应只有 look_back_days 行数据（+表头行+标题行）
    data_lines = [l for l in out.splitlines() if l and not l.startswith("#")]
    assert len(data_lines) == 6  # header + 5 行


@patch("astock.adapters.market_data.ak.stock_zh_a_hist",
       return_value=pd.DataFrame())
def test_no_data_raises(mock_hist):
    from tradingagents.dataflows.errors import NoMarketDataError
    with pytest.raises(NoMarketDataError):
        market_data.get_stock_data("600519", "2026-06-01", "2026-06-02")
