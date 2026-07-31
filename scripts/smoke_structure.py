"""结构分析真实数据冒烟：三级别缠论 + 威科夫特征（不调 LLM）。"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from astock.adapters import market_data  # noqa: E402
from astock.analysis import chanlun, wyckoff  # noqa: E402

symbol = sys.argv[1] if len(sys.argv) > 1 else "600519"
today = date.today().isoformat()
daily = market_data._daily_df(symbol, "2025-02-01", today)
weekly = market_data._weekly_df(symbol, "2023-08-01", today)
min30 = market_data._min30_df(symbol, today)
for df, lv in ((weekly, "周线"), (daily, "日线"), (min30, "30分钟")):
    r = chanlun.analyze_level(df, lv)
    print(f"[{lv}] {len(df)}根({df.attrs['source']}) 趋势={r.trend} "
          f"位置={r.position or '-'} 背驰={r.divergence} | {r.signal}")
print("[威科夫特征]")
print(wyckoff.features_markdown(wyckoff.extract_features(daily)))
print("SMOKE OK")
