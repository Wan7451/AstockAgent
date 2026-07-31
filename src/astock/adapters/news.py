"""A股新闻 vendor 实现。

签名对齐上游 yfinance/alpha_vantage 版：
- get_news(ticker, start_date, end_date)
- get_global_news(curr_date, look_back_days, limit)
个股新闻做日期过滤，防止未来新闻泄露到历史日期的分析（前视偏差）。
"""
from datetime import datetime, timedelta

import akshare as ak
import pandas as pd

from ._retry import with_retry
from .symbols import normalize, to_akshare


def _parse_time(v) -> datetime | None:
    s = str(v).strip()[:19]
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def get_news(ticker, start_date, end_date, *args, **kwargs) -> str:
    norm = normalize(ticker)
    df = with_retry(ak.stock_news_em, symbol=to_akshare(norm))
    lo = datetime.strptime(str(start_date), "%Y-%m-%d")
    hi = datetime.strptime(str(end_date), "%Y-%m-%d") + timedelta(days=1)
    rows = []
    for _, r in df.iterrows():
        t = _parse_time(r["发布时间"])
        if t is None or not (lo <= t < hi):
            continue
        content = str(r.get("新闻内容", "")).strip().replace("\n", " ")
        rows.append(f"- [{r['发布时间']}][{r.get('文章来源', '')}] "
                    f"{r['新闻标题']}\n  {content[:200]}")
    if not rows:
        return (f"{norm} 在 {start_date} ~ {end_date} 区间内无个股新闻"
                f"（东财个股新闻接口仅返回最近约10条，历史日期可能覆盖不到）。")
    return (f"# {norm} 个股新闻（{start_date} ~ {end_date}，东方财富源，"
            f"共{len(rows)}条）\n" + "\n".join(rows))


def get_global_news(curr_date, look_back_days=None, limit=None,
                    *args, **kwargs) -> str:
    df = with_retry(ak.stock_info_global_cls)
    limit = int(limit) if limit else 40
    lines = [f"# 市场要闻速览（财联社电报，抓取于分析时点，分析日 {curr_date}）",
             "# 注意：电报为实时快讯流，条目时间见方括号，请自行判断与分析日的相关性"]
    for _, r in df.head(limit).iterrows():
        ts = f"{r.get('发布日期', '')} {r.get('发布时间', '')}".strip()
        title = str(r.get("标题", "")).strip()
        content = str(r.get("内容", "")).strip().replace("\n", " ")
        text = title if title else content
        if title and content and content != title:
            text = f"{title}：{content}"
        lines.append(f"- [{ts}] {text[:260]}")
    return "\n".join(lines)
