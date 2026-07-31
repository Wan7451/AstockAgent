"""上游兼容性冒烟：更新 vendor/TradingAgents 后运行，全绿才算升级成功。

用法: .venv/bin/python scripts/smoke_upstream.py
"""
import inspect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


def main() -> None:
    from tradingagents.dataflows import interface
    from tradingagents.default_config import DEFAULT_CONFIG
    from tradingagents.graph.trading_graph import TradingAgentsGraph

    from astock.adapters import registry

    need = set(registry._METHODS)
    have = set(interface.VENDOR_METHODS)
    assert need <= have, f"上游缺少方法: {need - have}"

    sig = inspect.signature(TradingAgentsGraph.propagate)
    params = list(sig.parameters)
    assert params[:3] == ["self", "company_name", "trade_date"], f"propagate 签名变更: {sig}"

    assert "data_vendors" in DEFAULT_CONFIG, "DEFAULT_CONFIG 缺少 data_vendors"
    assert hasattr(interface, "route_to_vendor"), "route_to_vendor 不存在"
    assert hasattr(interface, "VENDOR_LIST"), "VENDOR_LIST 不存在"

    registry.register()
    for m in registry._METHODS:
        assert "akshare" in interface.VENDOR_METHODS[m], f"{m} 注册失败"

    from astock.config import build_config
    cfg = build_config()
    assert cfg["data_vendors"]["core_stock_apis"] == "akshare"

    print("SMOKE OK: 上游接口兼容，akshare vendor 注册正常")


if __name__ == "__main__":
    main()
