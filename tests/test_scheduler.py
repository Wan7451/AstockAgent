from datetime import date
from unittest.mock import patch

import pandas as pd

from astock import scheduler


def test_is_trading_day_with_calendar():
    fake = pd.DataFrame({"trade_date": ["2026-07-29", "2026-07-30"]})
    with patch("akshare.tool_trade_date_hist_sina", return_value=fake):
        assert scheduler.is_trading_day(date(2026, 7, 29)) is True
        assert scheduler.is_trading_day(date(2026, 7, 25)) is False


def test_is_trading_day_fallback_weekday():
    with patch("akshare.tool_trade_date_hist_sina", side_effect=RuntimeError):
        assert scheduler.is_trading_day(date(2026, 7, 29)) is True   # 周三
        assert scheduler.is_trading_day(date(2026, 7, 26)) is False  # 周日
