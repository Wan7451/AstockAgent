"""中国宏观数据 vendor 实现。

上游 fred 版签名为 get_macro_indicators(indicator, curr_date, look_back_days)，
FRED 指标代码与中国宏观体系不对应，故忽略 indicator 的具体值，
统一返回中国宏观核心指标包（LPR/PMI/社融/M2），供宏观/新闻分析师使用。
"""
import akshare as ak

from ._retry import with_retry


def get_macro_indicators(indicator=None, curr_date=None, look_back_days=None,
                         *args, **kwargs) -> str:
    parts = [f"# 中国宏观指标速览（请求指标: {indicator or '全部'}，分析日 {curr_date}）"]
    sources = [
        ("LPR 贷款市场报价利率", ak.macro_china_lpr,
         ["TRADE_DATE", "LPR1Y", "LPR5Y"], 6),
        ("官方制造业 PMI", ak.macro_china_pmi_yearly,
         ["日期", "今值", "预测值", "前值"], 6),
        ("社会融资规模增量（亿元）", ak.macro_china_shrzgm,
         ["月份", "社会融资规模增量", "其中-人民币贷款"], 6),
        ("货币供应量", ak.macro_china_money_supply,
         ["月份", "货币和准货币(M2)-数量(亿元)", "货币和准货币(M2)-同比增长",
          "货币(M1)-同比增长"], 6),
    ]
    for title, fn, cols, n in sources:
        try:
            df = with_retry(fn, retries=2, delay=1.0)
            keep = [c for c in cols if c in df.columns]
            parts.append(f"## {title}（最近{n}期）\n"
                         + df[keep].tail(n).to_string(index=False))
        except Exception as e:  # 宏观属可选类目，单项失败不阻断
            parts.append(f"## {title}\n获取失败: {e}")
    return "\n\n".join(parts)
