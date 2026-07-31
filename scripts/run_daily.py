"""手动触发一轮全池分析。用法:
.venv/bin/python scripts/run_daily.py [YYYY-MM-DD] [--force]
"""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")

from astock.scheduler import run_daily  # noqa: E402

if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    force = "--force" in sys.argv
    results = run_daily(args[0] if args else None, force=force)
    for r in results:
        print(f"{r['symbol']}: {r['decision'][:60]} -> {r['report_path']}")
    print(f"共 {len(results)} 只")
