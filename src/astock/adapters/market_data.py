"""A股日K与技术指标 vendor 实现。

签名与上游 yfinance 版对齐（route_to_vendor 透传参数）：
- get_stock_data(symbol, start_date, end_date)
- get_indicators(symbol, indicator, curr_date, look_back_days)
返回值一律是给 LLM 阅读的格式化文本。

数据源：东方财富（主，带重试）→ 新浪（降级，ValueCell 多源降级思路）。
"""
import logging
from datetime import datetime, timedelta

import akshare as ak
import pandas as pd

from ._retry import with_retry
from .symbols import exchange_of, normalize, to_akshare

logger = logging.getLogger(__name__)

_COL_MAP = {"日期": "date", "开盘": "open", "收盘": "close", "最高": "high",
            "最低": "low", "成交量": "volume", "成交额": "amount",
            "换手率": "turnover"}
_OUT_COLS = ["date", "open", "close", "high", "low", "volume", "amount",
             "turnover"]


def _no_data(symbol: str, detail: str):
    from tradingagents.dataflows.errors import NoMarketDataError
    return NoMarketDataError(symbol=str(symbol), canonical=normalize(symbol),
                             detail=detail)


def _em_daily(norm: str, start: str, end: str) -> pd.DataFrame:
    df = with_retry(ak.stock_zh_a_hist, symbol=to_akshare(norm),
                    period="daily", start_date=start, end_date=end,
                    adjust="qfq", retries=2, delay=1.5)
    return df.rename(columns=_COL_MAP)


def _sina_daily(norm: str, start: str, end: str) -> pd.DataFrame:
    sina_symbol = exchange_of(norm).lower() + to_akshare(norm)
    df = with_retry(ak.stock_zh_a_daily, symbol=sina_symbol,
                    start_date=start, end_date=end, adjust="qfq",
                    retries=2, delay=1.5)
    df["date"] = df["date"].astype(str)
    return df


def _daily_df(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    norm = normalize(symbol)
    start = str(start_date).replace("-", "")
    end = str(end_date).replace("-", "")
    df, src = None, None
    for name, fetch in (("东方财富", _em_daily), ("新浪", _sina_daily)):
        try:
            df, src = fetch(norm, start, end), name
            break
        except Exception as e:
            logger.warning("日K源 %s 获取 %s 失败: %s", name, norm, e)
    if df is None:
        raise _no_data(symbol, "东方财富与新浪源均获取失败")
    if df.empty:
        raise _no_data(symbol, f"{src} 未返回 {start_date}~{end_date} 日K数据")
    cols = [c for c in _OUT_COLS if c in df.columns]
    df = df[cols].reset_index(drop=True)
    df.attrs["source"] = src
    return df


def get_stock_data(symbol, start_date, end_date, *args, **kwargs) -> str:
    df = _daily_df(symbol, str(start_date), str(end_date))
    header = (f"# {normalize(symbol)} 日K数据（前复权，{df.attrs.get('source', '')}源）\n"
              f"# 区间: {start_date} ~ {end_date}，共 {len(df)} 根K线\n")
    text = header + df.to_csv(index=False)
    # 结构分析摘要搭车注入（缠论/威科夫，由 pipeline 预先构建；无则跳过）
    from ..analysis import structure
    digest = structure.get_digest(symbol)
    if digest:
        text += f"\n## 结构分析摘要（缠论/威科夫）\n{digest}\n"
    return text


def get_indicators(symbol, indicator, curr_date, look_back_days=30,
                   *args, **kwargs) -> str:
    from stockstats import wrap as ss_wrap
    end = str(curr_date)
    # 多取历史保证长周期指标计算有效
    lookback = int(look_back_days)
    extra = 400 if "200" in str(indicator) else 160
    start = (datetime.strptime(end, "%Y-%m-%d")
             - timedelta(days=lookback + extra)).strftime("%Y-%m-%d")
    df = _daily_df(symbol, start, end)
    sdf = ss_wrap(df.copy())
    try:
        series = sdf[str(indicator)]
    except Exception as e:
        raise ValueError(f"不支持的指标 {indicator!r}: {e}") from e
    out = pd.DataFrame({"date": df["date"].values,
                        str(indicator): pd.Series(series).values}).tail(lookback)
    return (f"# {normalize(symbol)} 技术指标 {indicator}"
            f"（最近{lookback}个交易日，基于前复权日K本地计算）\n"
            + out.to_csv(index=False))


# ---------- 结构分析用：周线 / 30分钟 ----------

def _weekly_df(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """周K：东财周线接口（主）→ 新浪日K本地重采样（降级）。"""
    norm = normalize(symbol)
    start = str(start_date).replace("-", "")
    end = str(end_date).replace("-", "")
    try:
        df = with_retry(ak.stock_zh_a_hist, symbol=to_akshare(norm),
                        period="weekly", start_date=start, end_date=end,
                        adjust="qfq", retries=2, delay=1.5)
        df = df.rename(columns=_COL_MAP)
        src = "东方财富"
    except Exception as e:
        logger.warning("周线源 东方财富 获取 %s 失败，降级新浪重采样: %s", norm, e)
        d = _sina_daily(norm, start, end)
        d["date"] = pd.to_datetime(d["date"])
        df = (d.set_index("date")
                .resample("W-FRI")
                .agg({"open": "first", "high": "max", "low": "min",
                      "close": "last", "volume": "sum", "amount": "sum"})
                .dropna(subset=["close"]).reset_index())
        df["date"] = df["date"].dt.strftime("%Y-%m-%d")
        src = "新浪(日K重采样)"
    if df.empty:
        raise _no_data(symbol, f"{src} 未返回周K数据")
    cols = [c for c in _OUT_COLS if c in df.columns]
    df = df[cols].reset_index(drop=True)
    df.attrs["source"] = src
    return df


def _min30_df(symbol: str, end_date: str) -> pd.DataFrame:
    """30分钟K：东财（主）→ 新浪（降级，约一年深度，数值为字符串）。

    截断到 end_date 当天 15:00，防前视。
    """
    norm = normalize(symbol)
    df, src = None, None
    try:
        start_dt = (datetime.strptime(str(end_date), "%Y-%m-%d")
                    - timedelta(days=240)).strftime("%Y-%m-%d 09:30:00")
        df = with_retry(ak.stock_zh_a_hist_min_em, symbol=to_akshare(norm),
                        period="30", adjust="qfq", start_date=start_dt,
                        end_date=f"{end_date} 15:00:00", retries=2, delay=1.5)
        df = df.rename(columns={**_COL_MAP, "时间": "date"})
        src = "东方财富"
    except Exception as e:
        logger.warning("30分钟源 东方财富 获取 %s 失败，降级新浪: %s", norm, e)
        sina_symbol = exchange_of(norm).lower() + to_akshare(norm)
        df = with_retry(ak.stock_zh_a_minute, symbol=sina_symbol,
                        period="30", adjust="qfq", retries=2, delay=1.5)
        df = df.rename(columns={"day": "date"})
        src = "新浪"
    if df is None or df.empty:
        raise _no_data(symbol, "30分钟K东财与新浪源均无数据")
    for c in ("open", "high", "low", "close", "volume"):
        df[c] = pd.to_numeric(df[c])
    df["date"] = df["date"].astype(str)
    df = df[df["date"] <= f"{end_date} 15:00:00"]
    cols = [c for c in _OUT_COLS if c in df.columns]
    df = df[cols].reset_index(drop=True)
    df.attrs["source"] = src
    return df
