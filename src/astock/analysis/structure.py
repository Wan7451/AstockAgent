"""结构分析统筹：三级别K线 → 缠论 + 威科夫 → 报告章节与决策摘要。

摘要缓存按规范化代码存放，由 market_data.get_stock_data 尾部搭车注入
市场分析师数据流（上游零修改）。
"""
import logging
from datetime import datetime, timedelta

from ..adapters import market_data
from ..adapters.symbols import normalize
from . import chanlun, wyckoff

logger = logging.getLogger(__name__)

_DIGESTS: dict[str, str] = {}   # norm -> digest，每次 build 覆盖


def get_digest(symbol: str) -> str | None:
    try:
        return _DIGESTS.get(normalize(str(symbol)))
    except ValueError:
        return None


def build(symbol: str, trade_date: str) -> dict:
    """返回 {chanlun_md, wyckoff_md, digest} 并缓存 digest。"""
    norm = normalize(symbol)
    end_dt = datetime.strptime(trade_date, "%Y-%m-%d")
    d_start = (end_dt - timedelta(days=550)).strftime("%Y-%m-%d")
    w_start = (end_dt - timedelta(days=1100)).strftime("%Y-%m-%d")
    daily = market_data._daily_df(norm, d_start, trade_date)
    weekly = market_data._weekly_df(norm, w_start, trade_date)
    min30 = market_data._min30_df(norm, trade_date)

    results = [chanlun.analyze_level(weekly, "周线"),
               chanlun.analyze_level(daily, "日线"),
               chanlun.analyze_level(min30, "30分钟")]
    chan_md = chanlun.render_report(results)
    wyckoff_md, wyckoff_summary = wyckoff.analyze(norm, daily)

    digest = f"缠论：{chanlun.render_digest(results)}\n威科夫：{wyckoff_summary}"
    _DIGESTS[norm] = digest
    return {"chanlun_md": chan_md, "wyckoff_md": wyckoff_md, "digest": digest}
