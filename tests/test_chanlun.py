"""缠论算法：合成K线精确断言。"""
import pandas as pd

from astock.analysis import chanlun


def _df(highs, lows):
    n = len(highs)
    return pd.DataFrame({"date": pd.date_range("2026-01-01", periods=n).astype(str),
                         "open": lows, "close": highs, "high": highs, "low": lows,
                         "volume": [100] * n})


def test_merge_inclusion():
    # 第2根被第1根完全包含，向上处理取高高：合并为一根
    bars = chanlun.merge_klines(_df([10, 9.5, 11], [5, 6, 7]))
    assert len(bars) == 2
    assert bars[0]["high"] == 10 and bars[0]["low"] == 6


def test_fractals():
    # 高点序列 11,12,13,12,11 → 中间为顶分型
    bars = chanlun.merge_klines(_df([11, 12, 13, 12, 11], [1, 2, 3, 2, 1]))
    fr = chanlun.find_fractals(bars)
    assert any(f.kind == "top" and f.price == 13 for f in fr)


def test_stroke_needs_gap():
    # 顶底分型间隔不足5根合并K线 → 不成笔
    highs = [10, 11, 12, 11, 10, 11]
    lows = [5, 6, 7, 6, 4, 5]
    fr = chanlun.find_fractals(chanlun.merge_klines(_df(highs, lows)))
    assert chanlun.build_strokes(fr) == []


def test_stroke_and_pivot():
    # 五段行情（升-降-升-降-升），中间三笔区间重叠形成中枢；
    # 末段上升保证最后的底分型两侧都有K线
    highs = (list(range(10, 21)) + list(range(19, 11, -1))
             + list(range(13, 19)) + list(range(17, 10, -1))
             + list(range(12, 20)))
    lows = [h - 1 for h in highs]
    fr = chanlun.find_fractals(chanlun.merge_klines(_df(highs, lows)))
    strokes = chanlun.build_strokes(fr)
    assert len(strokes) >= 3
    pivots = chanlun.find_pivots(strokes)
    assert pivots and pivots[0].low < pivots[0].high


def test_analyze_level_insufficient():
    r = chanlun.analyze_level(_df([10, 11], [9, 10]), "日线")
    assert r.trend == "数据不足"
