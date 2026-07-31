"""每日调度：交易日 15:30 自动分析自选股池全部股票。"""
import logging
from datetime import date, datetime
from pathlib import Path

from . import store
from .pipeline import ROOT, analyze

logger = logging.getLogger(__name__)


def is_trading_day(d: date | None = None) -> bool:
    """用新浪交易日历判断；接口失败时退化为周一~周五。"""
    d = d or date.today()
    try:
        import akshare as ak
        cal = ak.tool_trade_date_hist_sina()
        days = set(str(x) for x in cal["trade_date"].astype(str))
        return d.isoformat() in days
    except Exception as e:
        logger.warning("交易日历获取失败，退化为工作日判断: %s", e)
        return d.weekday() < 5


def run_daily(trade_date: str | None = None, force: bool = False) -> list[dict]:
    """串行分析自选股池全部股票（akshare 接口不宜并发），生成当日汇总。"""
    trade_date = trade_date or date.today().isoformat()
    if not force and not is_trading_day(date.fromisoformat(trade_date)):
        logger.info("%s 非交易日，跳过", trade_date)
        return []
    results = []
    for w in store.watchlist():
        sym = w["symbol"]
        aid = store.new_analysis(sym, trade_date)
        store.update_analysis(aid, status="running")
        try:
            res = analyze(sym, trade_date)
            store.update_analysis(
                aid, status="done", decision=res["decision"],
                report_path=res["report_path"],
                finished_at=datetime.now().isoformat(timespec="seconds"))
            results.append(res)
        except Exception as e:
            logger.exception("分析 %s 失败", sym)
            store.update_analysis(
                aid, status="failed", error=str(e)[:500],
                finished_at=datetime.now().isoformat(timespec="seconds"))
            results.append({"symbol": sym, "trade_date": trade_date,
                            "decision": f"FAILED: {e}", "report_path": ""})
    _write_summary(trade_date, results)
    return results


def _write_summary(trade_date: str, results: list[dict]) -> None:
    if not results:
        return
    out = Path(ROOT) / "reports" / trade_date / "daily_summary.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# 每日决策汇总 — {trade_date}", "",
             "| 股票 | 决策信号 | 报告 |", "|---|---|---|"]
    for r in results:
        link = Path(r["report_path"]).name if r["report_path"] else "-"
        lines.append(f"| {r['symbol']} | {r['decision'][:80]} | {link} |")
    lines.append("\n> 仅供研究参考，不构成投资建议。")
    out.write_text("\n".join(lines), encoding="utf-8")


def start_background_scheduler():
    """启动 APScheduler：周一~五 15:30（Asia/Shanghai）触发。"""
    from apscheduler.schedulers.background import BackgroundScheduler
    sched = BackgroundScheduler(timezone="Asia/Shanghai")
    sched.add_job(run_daily, "cron", day_of_week="mon-fri",
                  hour=15, minute=30, id="daily_analysis")
    sched.start()
    logger.info("每日调度已启动：交易日 15:30 自动分析自选股池")
    return sched
