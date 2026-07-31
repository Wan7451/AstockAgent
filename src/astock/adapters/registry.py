"""把 akshare vendor 注册进上游路由表 + 修补上游 yfinance 硬编码路径。

必须在任何分析发起前调用 register()。上游源码零修改：
1. VENDOR_METHODS 插入 "akshare" 实现（route_to_vendor 按配置路由）；
2. 运行时补丁 load_ohlcv：上游 get_verified_market_snapshot（市场分析师
   的防幻觉校验工具）直连 Yahoo Finance，不走 vendor 路由，A股代码在
   Yahoo 无数据会导致流水线中断。补丁对 A股代码改用 akshare 日K，
   非 A股代码原样走 Yahoo。三个模块各自持有 load_ohlcv 的名字绑定，
   必须逐一替换。
"""
from datetime import date, timedelta
from functools import lru_cache, wraps

import pandas as pd
from tradingagents.dataflows import interface

from . import fundamentals, insider, macro, market_data, news, symbols

_METHODS = {
    "get_stock_data": market_data.get_stock_data,
    "get_indicators": market_data.get_indicators,
    "get_fundamentals": fundamentals.get_fundamentals,
    "get_balance_sheet": fundamentals.get_balance_sheet,
    "get_income_statement": fundamentals.get_income_statement,
    "get_cashflow": fundamentals.get_cashflow,
    "get_news": news.get_news,
    "get_global_news": news.get_global_news,
    "get_insider_transactions": insider.get_insider_transactions,
    "get_macro_indicators": macro.get_macro_indicators,
}

_orig_load_ohlcv = None


@lru_cache(maxsize=64)
def _astock_ohlcv(norm: str, cache_day: str) -> pd.DataFrame:
    """A股近2年日K，转成上游 load_ohlcv 的返回格式（大写列名）。"""
    end = date.today()
    start = end - timedelta(days=730)
    df = market_data._daily_df(norm, start.isoformat(), end.isoformat())
    return pd.DataFrame({
        "Date": pd.to_datetime(df["date"]),
        "Open": pd.to_numeric(df["open"]),
        "High": pd.to_numeric(df["high"]),
        "Low": pd.to_numeric(df["low"]),
        "Close": pd.to_numeric(df["close"]),
        "Volume": pd.to_numeric(df["volume"]),
    })


def _patched_load_ohlcv(symbol, curr_date):
    try:
        norm = symbols.normalize(str(symbol))
    except ValueError:  # 非A股代码，走原 Yahoo 实现
        return _orig_load_ohlcv(symbol, curr_date)
    data = _astock_ohlcv(norm, date.today().isoformat()).copy()
    data = data[data["Date"] <= pd.to_datetime(curr_date)]
    if data.empty:
        from tradingagents.dataflows.errors import NoMarketDataError
        raise NoMarketDataError(str(symbol), norm,
                                f"akshare 无 {curr_date} 及之前的日K数据")
    return data.reset_index(drop=True)


def _tolerant(impl):
    """无效代码不抛异常，返回纠正提示——LLM 会自行改用正确代码重试，
    避免上游 docstring 示例（AAPL/TSM）误导分析师时打死整个任务。"""
    @wraps(impl)
    def wrapper(*args, **kwargs):
        try:
            return impl(*args, **kwargs)
        except ValueError as e:
            if "无法识别的A股代码" in str(e):
                return (f"工具调用错误：{e}。本系统仅支持A股代码"
                        "（如 600519.SH、002384.SZ），请改用当前分析标的的"
                        "A股代码重新调用本工具，不要使用美股代码。")
            raise
    return wrapper


def register() -> None:
    global _orig_load_ohlcv
    if "akshare" not in interface.VENDOR_LIST:
        interface.VENDOR_LIST.append("akshare")
    for method, impl in _METHODS.items():
        if method not in interface.VENDOR_METHODS:
            raise RuntimeError(
                f"上游已移除方法 {method}，请更新适配层（运行 scripts/smoke_upstream.py 排查）")
        interface.VENDOR_METHODS[method]["akshare"] = _tolerant(impl)

    # 修补 load_ohlcv 的全部名字绑定（from-import 按名绑定，需逐模块替换）
    from tradingagents.dataflows import (market_data_validator,
                                         stockstats_utils, y_finance)
    if _orig_load_ohlcv is None:
        _orig_load_ohlcv = stockstats_utils.load_ohlcv
        stockstats_utils.load_ohlcv = _patched_load_ohlcv
        market_data_validator.load_ohlcv = _patched_load_ohlcv
        y_finance.load_ohlcv = _patched_load_ohlcv
