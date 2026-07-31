from unittest.mock import patch

from tradingagents.dataflows import interface

from astock.adapters import registry


def test_register_inserts_all_methods():
    registry.register()
    assert "akshare" in interface.VENDOR_LIST
    for method in registry._METHODS:
        assert "akshare" in interface.VENDOR_METHODS[method], method


def test_route_to_vendor_reaches_akshare():
    registry.register()
    from astock.config import build_config
    cfg = build_config()
    # route_to_vendor 读取全局配置里的 data_vendors
    from tradingagents.dataflows.config import set_config
    set_config(cfg)
    with patch.dict(interface.VENDOR_METHODS["get_stock_data"],
                    {"akshare": lambda *a, **kw: "AKSHARE_CALLED"}):
        out = interface.route_to_vendor("get_stock_data",
                                        "600519", "2026-07-01", "2026-07-29")
    assert out == "AKSHARE_CALLED"


def test_config_models():
    from astock.config import build_config
    cfg = build_config()
    assert cfg["llm_provider"] == "deepseek"
    assert cfg["quick_think_llm"].startswith("deepseek-v4")
    assert cfg["data_vendors"]["core_stock_apis"] == "akshare"


def test_load_ohlcv_patched_for_astock():
    from unittest.mock import patch as mpatch

    import pandas as pd

    registry.register()
    from tradingagents.dataflows import market_data_validator, stockstats_utils
    assert stockstats_utils.load_ohlcv is registry._patched_load_ohlcv
    assert market_data_validator.load_ohlcv is registry._patched_load_ohlcv

    fake = pd.DataFrame({"date": ["2026-07-28", "2026-07-29", "2026-07-30"],
                         "open": [1, 2, 3], "close": [1, 2, 3],
                         "high": [1, 2, 3], "low": [1, 2, 3],
                         "volume": [10, 20, 30], "amount": [1, 2, 3],
                         "turnover": [.1, .2, .3]})
    registry._astock_ohlcv.cache_clear()
    with mpatch.object(registry.market_data, "_daily_df", return_value=fake):
        out = registry._patched_load_ohlcv("600519", "2026-07-29")
    assert list(out.columns) == ["Date", "Open", "High", "Low", "Close", "Volume"]
    assert len(out) == 2  # 2026-07-30 被前视过滤裁掉
