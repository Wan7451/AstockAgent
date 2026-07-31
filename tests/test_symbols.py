from astock.adapters.symbols import normalize, to_akshare, to_em_prefixed, exchange_of
import pytest

def test_normalize_variants():
    for raw in ["600519", "sh600519", "SH600519", "600519.SH", "600519.ss"]:
        assert normalize(raw) == "600519.SH"
    assert normalize("000001") == "000001.SZ"
    assert normalize("300750.sz") == "300750.SZ"
    assert normalize("688981") == "688981.SH"
    assert normalize("830799") == "830799.BJ"

def test_normalize_invalid():
    for bad in ["AAPL", "60051", "6005199", ""]:
        with pytest.raises(ValueError):
            normalize(bad)

def test_downstream_formats():
    assert to_akshare("600519.SH") == "600519"
    assert to_em_prefixed("600519.SH") == "SH600519"
    assert exchange_of("000001.SZ") == "SZ"
