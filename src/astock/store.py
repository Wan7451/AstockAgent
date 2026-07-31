"""SQLite 存储：自选股池 + 分析任务记录。标准库 sqlite3，无额外依赖。"""
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "astock.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS watchlist(
  symbol TEXT PRIMARY KEY,
  name TEXT DEFAULT '',
  grp TEXT DEFAULT '默认',
  added_at TEXT);
CREATE TABLE IF NOT EXISTS analyses(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  symbol TEXT,
  trade_date TEXT,
  status TEXT DEFAULT 'queued',
  decision TEXT,
  report_path TEXT,
  error TEXT,
  created_at TEXT,
  finished_at TEXT);
CREATE INDEX IF NOT EXISTS idx_analyses_date ON analyses(trade_date);
"""


@contextmanager
def conn(db_path: Path | str | None = None):
    p = Path(db_path or DB_PATH)
    p.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(p)
    c.row_factory = sqlite3.Row
    c.executescript(_SCHEMA)
    try:
        yield c
        c.commit()
    finally:
        c.close()


def add_watch(symbol, name="", grp="默认", db_path=None):
    with conn(db_path) as c:
        c.execute("INSERT OR IGNORE INTO watchlist VALUES(?,?,?,?)",
                  (symbol, name, grp, datetime.now().isoformat(timespec="seconds")))


def remove_watch(symbol, db_path=None):
    with conn(db_path) as c:
        c.execute("DELETE FROM watchlist WHERE symbol=?", (symbol,))


def watchlist(db_path=None):
    with conn(db_path) as c:
        return [dict(r) for r in
                c.execute("SELECT * FROM watchlist ORDER BY grp, symbol")]


def new_analysis(symbol, trade_date, db_path=None):
    with conn(db_path) as c:
        cur = c.execute(
            "INSERT INTO analyses(symbol,trade_date,created_at) VALUES(?,?,?)",
            (symbol, trade_date, datetime.now().isoformat(timespec="seconds")))
        return cur.lastrowid


def update_analysis(aid, db_path=None, **fields):
    if not fields:
        return
    sets = ",".join(f"{k}=?" for k in fields)
    with conn(db_path) as c:
        c.execute(f"UPDATE analyses SET {sets} WHERE id=?",
                  (*fields.values(), aid))


def get_analysis(aid, db_path=None):
    with conn(db_path) as c:
        r = c.execute("SELECT * FROM analyses WHERE id=?", (aid,)).fetchone()
        return dict(r) if r else None


def list_analyses(limit=100, db_path=None):
    with conn(db_path) as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM analyses ORDER BY id DESC LIMIT ?", (limit,))]
