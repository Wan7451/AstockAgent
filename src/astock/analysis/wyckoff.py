"""威科夫量价分析：客观特征算法提取（防幻觉）+ DeepSeek 阶段判定。"""
import logging
import os
import re

import pandas as pd

logger = logging.getLogger(__name__)

_SYSTEM = (
    "你是威科夫方法论（Wyckoff Method）专家。分析框架：吸筹/派发结构与A-E阶段划分、"
    "三大法则（供需法则、因果法则、努力与结果法则）、关键事件（PS/SC/AR/ST/Spring/"
    "Test/SOS/LPS/UTAD/SOW）。只依据用户提供的客观特征数字推理，禁止编造任何价格或日期。"
    "输出要求：第一行必须是「【判定】阶段：xxx（置信度：高/中/低）」，随后分节输出："
    "关键证据（必须引用特征表中的数字）、多空含义、判定失效条件。用中文。")


def extract_features(daily: pd.DataFrame, window: int = 120) -> dict:
    """近 window 日量价客观特征，全部数字算法产出。"""
    df = daily.tail(window).reset_index(drop=True).copy()
    for c in ("open", "high", "low", "close", "volume"):
        df[c] = pd.to_numeric(df[c])
    box_high, box_low = float(df["high"].max()), float(df["low"].min())
    close = float(df["close"].iloc[-1])
    pos_pct = ((close - box_low) / (box_high - box_low) * 100
               if box_high > box_low else 50.0)
    chg = df["close"].pct_change()
    vol_ma = df["volume"].rolling(20).mean()
    up_expand = int(((chg > 0.01) & (df["volume"] > 1.5 * vol_ma)).sum())
    down_shrink = int(((chg < -0.005) & (df["volume"] < 0.8 * vol_ma)).sum())
    vol_recent = float(df["volume"].tail(20).mean())
    vol_prev = float(df["volume"].iloc[-80:-20].mean()) if len(df) >= 80 else vol_recent
    events = []
    for i in range(1, len(df)):
        v, vm = df["volume"].iloc[i], vol_ma.iloc[i]
        if pd.isna(vm) or vm == 0:
            continue
        c, d = float(chg.iloc[i]), str(df["date"].iloc[i])
        lo, hi, cl = df["low"].iloc[i], df["high"].iloc[i], df["close"].iloc[i]
        if c < -0.04 and v > 2 * vm:
            events.append(f"{d} 恐慌抛售候选(SC)：跌{c:.1%}，量为20日均量{v / vm:.1f}倍")
        elif c > 0.04 and v > 2 * vm:
            events.append(f"{d} 急涨候选(AR/SOS)：涨{c:.1%}，量为20日均量{v / vm:.1f}倍")
        elif lo <= box_low * 1.01 and cl >= lo * 1.02:
            events.append(f"{d} 弹簧候选(Spring)：下探箱体下沿{lo:.2f}后收回至{cl:.2f}")
        elif hi >= box_high * 0.99 and cl <= hi * 0.98:
            events.append(f"{d} 假突破候选(UTAD)：冲高箱体上沿{hi:.2f}后回落至{cl:.2f}")
    return {"window": len(df), "box_high": box_high, "box_low": box_low,
            "close": close, "pos_pct": pos_pct, "up_expand_days": up_expand,
            "down_shrink_days": down_shrink, "vol_recent": vol_recent,
            "vol_prev": vol_prev, "events": events[-10:]}


def features_markdown(f: dict) -> str:
    vol_chg = (f["vol_recent"] / f["vol_prev"] - 1) * 100 if f["vol_prev"] else 0
    lines = [f"近{f['window']}个交易日量价特征（算法客观计算）：\n",
             "| 特征 | 数值 |", "|---|---|",
             f"| 价格箱体 | {f['box_low']:.2f} ~ {f['box_high']:.2f} |",
             f"| 现价及箱体内位置 | {f['close']:.2f}（{f['pos_pct']:.0f}%分位） |",
             f"| 放量上涨天数(涨>1%且量>1.5倍均量) | {f['up_expand_days']} |",
             f"| 缩量回调天数(跌>0.5%且量<0.8倍均量) | {f['down_shrink_days']} |",
             f"| 近20日均量较前60日 | {vol_chg:+.0f}% |"]
    if f["events"]:
        lines.append("\n关键事件候选（按量价规则筛选）：")
        lines += [f"- {e}" for e in f["events"]]
    else:
        lines.append("\n关键事件候选：无")
    return "\n".join(lines)


def judge_with_llm(feats_md: str, symbol: str) -> str:
    from openai import OpenAI

    from ..config import DEEP_MODEL
    client = OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"],
                    base_url="https://api.deepseek.com")
    resp = client.chat.completions.create(
        model=DEEP_MODEL, temperature=0.2, timeout=180,
        messages=[{"role": "system", "content": _SYSTEM},
                  {"role": "user", "content": f"标的：{symbol}\n\n{feats_md}"}])
    return resp.choices[0].message.content


def analyze(symbol: str, daily: pd.DataFrame) -> tuple[str, str]:
    """返回 (完整章节 markdown, 一句话摘要)。LLM 失败降级为纯特征表。"""
    feats_md = features_markdown(extract_features(daily))
    try:
        verdict = judge_with_llm(feats_md, symbol)
    except Exception as e:
        logger.warning("威科夫 LLM 判定失败: %s", e)
        return (feats_md + "\n\n> LLM 判定失败，本节仅列客观量价特征。",
                "威科夫判定失败")
    m = re.search(r"【判定】(.+)", verdict)
    summary = m.group(1).strip() if m else "见威科夫章节"
    return verdict + "\n\n### 客观特征依据\n\n" + feats_md, summary
