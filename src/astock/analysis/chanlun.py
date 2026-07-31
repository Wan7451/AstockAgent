"""缠论结构算法（简化标准）：包含合并 → 分型 → 笔 → 中枢 → 背驰。

输入统一为含 date/open/high/low/close/volume 列的升序 DataFrame，
价位全部来自真实K线，零 LLM 参与、零幻觉。
"""
from dataclasses import dataclass

import pandas as pd


@dataclass
class Fractal:
    idx: int        # 合并后K线序号
    date: str
    kind: str       # "top" / "bottom"
    price: float


@dataclass
class Stroke:
    start: Fractal
    end: Fractal
    direction: str  # "up" / "down"


@dataclass
class Pivot:
    start_date: str
    end_date: str
    low: float      # 中枢下沿 ZD
    high: float     # 中枢上沿 ZG


@dataclass
class LevelResult:
    level: str
    trend: str
    n_strokes: int
    pivots: list
    position: str
    divergence: str
    signal: str
    close: float


def merge_klines(df: pd.DataFrame) -> list[dict]:
    """包含关系合并：向上取高高，向下取低低。"""
    bars, direction = [], 1
    for row in df.itertuples():
        bar = {"date": str(row.date), "high": float(row.high), "low": float(row.low)}
        if not bars:
            bars.append(bar)
            continue
        prev = bars[-1]
        contains = ((bar["high"] <= prev["high"] and bar["low"] >= prev["low"])
                    or (bar["high"] >= prev["high"] and bar["low"] <= prev["low"]))
        if contains:
            if direction >= 0:
                prev["high"] = max(prev["high"], bar["high"])
                prev["low"] = max(prev["low"], bar["low"])
            else:
                prev["high"] = min(prev["high"], bar["high"])
                prev["low"] = min(prev["low"], bar["low"])
            prev["date"] = bar["date"]
        else:
            direction = 1 if bar["high"] > prev["high"] else -1
            bars.append(bar)
    return bars


def find_fractals(bars: list[dict]) -> list[Fractal]:
    out = []
    for i in range(1, len(bars) - 1):
        a, b, c = bars[i - 1], bars[i], bars[i + 1]
        if b["high"] > a["high"] and b["high"] > c["high"]:
            out.append(Fractal(i, b["date"], "top", b["high"]))
        elif b["low"] < a["low"] and b["low"] < c["low"]:
            out.append(Fractal(i, b["date"], "bottom", b["low"]))
    return out


def build_strokes(fractals: list[Fractal]) -> list[Stroke]:
    """顶底交替成笔：同向取更极端，异向要求间隔≥4根合并K线（即≥5根K线跨度）。"""
    if not fractals:
        return []
    valid = [fractals[0]]
    for f in fractals[1:]:
        last = valid[-1]
        if f.kind == last.kind:
            better = f.price > last.price if f.kind == "top" else f.price < last.price
            if better:
                valid[-1] = f
        elif f.idx - last.idx >= 4:
            valid.append(f)
    return [Stroke(a, b, "up" if b.kind == "top" else "down")
            for a, b in zip(valid, valid[1:])]


def find_pivots(strokes: list[Stroke]) -> list[Pivot]:
    """连续三笔重叠区间 [max(低), min(高)]，非空成中枢。"""
    pivots, i = [], 0
    while i + 2 < len(strokes):
        seg = strokes[i:i + 3]
        zd = max(min(s.start.price, s.end.price) for s in seg)
        zg = min(max(s.start.price, s.end.price) for s in seg)
        if zd < zg:
            pivots.append(Pivot(seg[0].start.date, seg[2].end.date, zd, zg))
            i += 3
        else:
            i += 1
    return pivots


def _macd_hist(close: pd.Series) -> pd.Series:
    fast = close.ewm(span=12, adjust=False).mean()
    slow = close.ewm(span=26, adjust=False).mean()
    dif = fast - slow
    return (dif - dif.ewm(span=9, adjust=False).mean()) * 2


def check_divergence(df: pd.DataFrame, strokes: list[Stroke]) -> str:
    """末笔与前一同向笔：价格创新极值而 MACD 柱面积衰竭 → 背驰。"""
    if len(strokes) < 3:
        return "无"
    hist = _macd_hist(pd.to_numeric(df["close"]))
    dates = df["date"].astype(str)

    def area(s: Stroke) -> float:
        seg = hist[(dates >= s.start.date) & (dates <= s.end.date)]
        return float(seg[seg > 0].sum()) if s.direction == "up" else float(-seg[seg < 0].sum())

    last = strokes[-1]
    prev = next((s for s in reversed(strokes[:-1]) if s.direction == last.direction), None)
    if prev is None:
        return "无"
    if last.direction == "up" and last.end.price > prev.end.price and area(last) < area(prev):
        return "顶背驰"
    if last.direction == "down" and last.end.price < prev.end.price and area(last) < area(prev):
        return "底背驰"
    return "无"


def _signal(trend: str, position: str, divergence: str) -> str:
    if divergence == "底背驰":
        return "潜在一类买点（下跌力度衰竭），关注企稳确认"
    if divergence == "顶背驰":
        return "潜在一类卖点（上涨力度衰竭），注意兑现风险"
    if trend == "上涨" and position == "中枢上方":
        return "趋势延续，回踩中枢上沿为三类买点观察区"
    if trend == "下跌" and position == "中枢下方":
        return "趋势向下，反抽中枢下沿为三类卖点观察区"
    if position == "中枢内":
        return "中枢震荡，等待方向选择"
    return "结构中性，观望"


def analyze_level(df: pd.DataFrame, level: str) -> LevelResult:
    close = float(pd.to_numeric(df["close"]).iloc[-1]) if len(df) else 0.0
    if len(df) < 30:
        return LevelResult(level, "数据不足", 0, [], "", "无", "K线不足30根，跳过", close)
    strokes = build_strokes(find_fractals(merge_klines(df)))
    pivots = find_pivots(strokes)
    if len(pivots) >= 2:
        c0 = (pivots[-2].low + pivots[-2].high) / 2
        c1 = (pivots[-1].low + pivots[-1].high) / 2
        trend = "上涨" if c1 > c0 else ("下跌" if c1 < c0 else "盘整")
    elif pivots:
        trend = "盘整"
    elif strokes:
        trend = "上涨" if strokes[-1].direction == "up" else "下跌"
    else:
        trend = "盘整"
    if pivots:
        p = pivots[-1]
        position = ("中枢上方" if close > p.high
                    else "中枢下方" if close < p.low else "中枢内")
    else:
        position = ""
    divergence = check_divergence(df, strokes)
    return LevelResult(level, trend, len(strokes), pivots, position,
                       divergence, _signal(trend, position, divergence), close)


def render_report(results: list[LevelResult]) -> str:
    lines = ["按缠论简化标准（包含合并/分型/笔/中枢/MACD背驰）本地算法计算，价位客观无幻觉。\n"]
    for r in results:
        lines.append(f"### {r.level}级别")
        if r.trend == "数据不足":
            lines.append(f"- {r.signal}")
            continue
        lines.append(f"- 趋势：**{r.trend}**（笔数 {r.n_strokes}）")
        if r.pivots:
            p = r.pivots[-1]
            lines.append(f"- 最近中枢：[{p.low:.2f}, {p.high:.2f}]"
                         f"（{p.start_date} ~ {p.end_date}），现价 {r.close:.2f} 位于**{r.position}**")
        lines.append(f"- 背驰：{r.divergence}")
        lines.append(f"- 提示：{r.signal}")
    lines.append("\n### 三级别联立结论\n" + render_digest(results))
    return "\n".join(lines)


def render_digest(results: list[LevelResult]) -> str:
    parts = []
    for r in results:
        if r.trend == "数据不足":
            parts.append(f"{r.level}数据不足")
        else:
            seg = f"{r.level}{r.trend}"
            if r.position:
                seg += f"({r.position})"
            if r.divergence != "无":
                seg += f"，{r.divergence}"
            parts.append(seg)
    return "；".join(parts) + "。周线定势、日线主分析、30分钟找买卖点。"
