"""内部人交易 vendor：A股口径 = 高管增减持 + 大宗交易（均为东财源）。"""
from datetime import date, timedelta
from functools import lru_cache

import akshare as ak

from ._retry import with_retry
from .symbols import normalize, to_akshare


@lru_cache(maxsize=1)
def _ggcg_all(cache_key: str):
    """全市场高管增减持表约14万行，按天缓存避免重复拉取。"""
    return with_retry(ak.stock_ggcg_em, symbol="全部")


def get_insider_transactions(ticker, *args, **kwargs) -> str:
    norm = normalize(ticker)
    code = to_akshare(norm)
    parts = [f"# {norm} 内部人交易（A股口径：高管增减持 + 大宗交易）"]
    try:
        ggcg = _ggcg_all(date.today().isoformat())
        mine = ggcg[ggcg["代码"].astype(str) == code]
        cols = ["股东名称", "持股变动信息-增减", "持股变动信息-变动数量",
                "持股变动信息-占总股本比例", "变动开始日", "变动截止日", "公告日"]
        cols = [c for c in cols if c in mine.columns]
        parts.append("## 高管增减持（近20条）\n"
                     + (mine[cols].head(20).to_string(index=False)
                        if not mine.empty else "近期无高管增减持记录"))
    except Exception as e:
        parts.append(f"## 高管增减持\n获取失败: {e}")
    try:
        end = date.today()
        start = end - timedelta(days=180)
        dzjy = with_retry(ak.stock_dzjy_mrmx, symbol="A股",
                          start_date=start.strftime("%Y%m%d"),
                          end_date=end.strftime("%Y%m%d"))
        mine2 = dzjy[dzjy["证券代码"].astype(str) == code]
        cols2 = ["交易日期", "成交价", "折溢率", "成交量", "成交额",
                 "买方营业部", "卖方营业部"]
        cols2 = [c for c in cols2 if c in mine2.columns]
        parts.append("## 大宗交易（近180天）\n"
                     + (mine2[cols2].head(20).to_string(index=False)
                        if not mine2.empty else "近180天无大宗交易记录"))
    except Exception as e:
        parts.append(f"## 大宗交易\n获取失败: {e}")
    return "\n\n".join(parts)
