"""单股分析入口：注册 vendor → 跑完整 TradingAgents 流水线 → 落 Markdown 报告。"""
from datetime import date
from pathlib import Path

from .adapters import registry
from .adapters.symbols import normalize
from .config import build_config

ROOT = Path(__file__).resolve().parent.parent.parent
DISCLAIMER = ("\n\n---\n> 本报告由多智能体系统自动生成，仅供研究参考，"
              "不构成任何投资建议。最终交易决策请人工判断。"
              "数据来源：akshare（东方财富/新浪/雪球/财联社等公开接口）。")

_SECTIONS = [
    ("market_report", "技术面分析"),
    ("sentiment_report", "情绪分析"),
    ("news_report", "新闻分析"),
    ("fundamentals_report", "基本面分析"),
    ("investment_plan", "研究经理裁决（多空辩论结论）"),
    ("trader_investment_plan", "交易员方案"),
    ("final_trade_decision", "风控终审"),
]


def analyze(symbol: str, trade_date: str | None = None,
            reports_dir: Path | str | None = None, progress_cb=None) -> dict:
    from tradingagents.graph.trading_graph import TradingAgentsGraph

    registry.register()
    norm = normalize(symbol)
    trade_date = trade_date or date.today().isoformat()
    if progress_cb:
        progress_cb("building", f"初始化多智能体图 {norm} @ {trade_date}")
    graph = TradingAgentsGraph(config=build_config())
    if progress_cb:
        progress_cb("running", "流水线执行中（4分析师→多空辩论→交易员→风控）")
    final_state, decision = graph.propagate(norm, trade_date)

    out_dir = Path(reports_dir or ROOT / "reports") / trade_date
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{norm.replace('.', '_')}.md"
    lines = [f"# {norm} 决策报告 — {trade_date}",
             f"\n## 最终决策信号\n\n**{decision}**\n"]
    for key, title in _SECTIONS:
        content = final_state.get(key)
        if content:
            lines.append(f"\n## {title}\n\n{content}")
    path.write_text("\n".join(lines) + DISCLAIMER, encoding="utf-8")
    if progress_cb:
        progress_cb("done", str(path))
    return {"symbol": norm, "trade_date": trade_date,
            "decision": str(decision), "report_path": str(path)}
