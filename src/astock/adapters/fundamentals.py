"""A股基本面 vendor 实现（对齐上游 yfinance 版签名，参数名 ticker）。

数据源策略：
- 公司概览：雪球（stock_individual_basic_info_xq，稳定）＋东财实时估值（可选，域名偶发不可用）
- 财务指标：新浪（stock_financial_analysis_indicator）
- 三大报表：东财 datacenter（stock_*_sheet_by_report_em，按报告期）
"""
import akshare as ak
import pandas as pd

from ._retry import with_retry
from .symbols import normalize, to_akshare, to_em_prefixed


def get_fundamentals(ticker, curr_date=None, *args, **kwargs) -> str:
    norm = normalize(ticker)
    parts = [f"# {norm} 基本面概览"]
    try:
        xq = with_retry(ak.stock_individual_basic_info_xq,
                        symbol=to_em_prefixed(norm))
        keep = xq[xq["item"].isin([
            "org_name_cn", "org_short_name_cn", "main_operation_business",
            "org_cn_introduction", "legal_representative", "established_date",
            "listed_date", "actual_controller", "classi_name",
        ])]
        parts.append("## 公司简介（雪球）\n" + keep.to_string(index=False))
    except Exception as e:
        parts.append(f"## 公司简介\n获取失败: {e}")
    try:
        info = with_retry(ak.stock_individual_info_em, symbol=to_akshare(norm),
                          retries=2, delay=1.0)
        parts.append("## 实时概况（东方财富：市值/市盈率/行业等）\n"
                     + info.to_string(index=False))
    except Exception as e:
        parts.append(f"## 实时概况（东财）\n获取失败（域名偶发不可用，可忽略）: {e}")
    try:
        fin = with_retry(ak.stock_financial_analysis_indicator,
                         symbol=to_akshare(norm), start_year="2023")
        fin = fin.sort_values("日期", ascending=False).head(6)
        key_cols = [c for c in [
            "日期", "摊薄每股收益(元)", "每股净资产_调整后(元)",
            "每股经营性现金流(元)", "总资产利润率(%)", "主营业务利润率(%)",
            "净资产收益率(%)", "主营业务收入增长率(%)", "净利润增长率(%)",
            "资产负债率(%)", "流动比率", "存货周转率(次)",
        ] if c in fin.columns]
        parts.append("## 主要财务指标（新浪，最近6期）\n"
                     + fin[key_cols].to_string(index=False))
    except Exception as e:
        parts.append(f"## 主要财务指标\n获取失败: {e}")
    return "\n\n".join(parts)


def _em_sheet(fetcher, ticker, title, periods=4) -> str:
    norm = normalize(ticker)
    df = with_retry(fetcher, symbol=to_em_prefixed(norm))
    df = df.head(periods)
    # 报表列数上百，去掉全空列并转置，行=科目 列=报告期，便于 LLM 阅读
    df = df.dropna(axis=1, how="all")
    dates = df["REPORT_DATE_NAME"].tolist() if "REPORT_DATE_NAME" in df else \
        df["REPORT_DATE"].astype(str).str[:10].tolist()
    meta_cols = {"SECUCODE", "SECURITY_CODE", "SECURITY_NAME_ABBR", "ORG_CODE",
                 "ORG_TYPE", "REPORT_TYPE", "SECURITY_TYPE_CODE", "NOTICE_DATE",
                 "UPDATE_DATE", "CURRENCY", "REPORT_DATE", "REPORT_DATE_NAME"}
    body = df[[c for c in df.columns if c not in meta_cols]].T
    body.columns = dates
    return (f"# {norm} {title}（东方财富按报告期，最近{len(df)}期）\n"
            f"# 单位：元；行为科目（东财英文字段名），列为报告期\n"
            + body.to_string())


def get_balance_sheet(ticker, freq="quarterly", curr_date=None, *a, **kw) -> str:
    return _em_sheet(ak.stock_balance_sheet_by_report_em, ticker, "资产负债表")


def get_income_statement(ticker, freq="quarterly", curr_date=None, *a, **kw) -> str:
    return _em_sheet(ak.stock_profit_sheet_by_report_em, ticker, "利润表")


def get_cashflow(ticker, freq="quarterly", curr_date=None, *a, **kw) -> str:
    return _em_sheet(ak.stock_cash_flow_sheet_by_report_em, ticker, "现金流量表")
