"""FastAPI 后端：自选股管理 / 按需分析（后台线程 + SSE 进度）/ 报告查看。

启动: .venv/bin/uvicorn astock.web.app:app --app-dir src --port 8620
启动时自动开启每日调度（交易日 15:30 全池分析）。
"""
import logging
import queue
import threading
from contextlib import asynccontextmanager
from datetime import date, datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import (FileResponse, PlainTextResponse,
                               StreamingResponse)
from pydantic import BaseModel

from .. import store
from ..adapters.symbols import normalize
from ..pipeline import ROOT, analyze

logger = logging.getLogger(__name__)
_events: dict[int, queue.Queue] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    from ..scheduler import start_background_scheduler
    sched = start_background_scheduler()
    yield
    sched.shutdown(wait=False)


app = FastAPI(title="astock-agent", lifespan=lifespan)


class WatchReq(BaseModel):
    symbol: str
    name: str = ""
    grp: str = "默认"


class AnalyzeReq(BaseModel):
    symbol: str
    trade_date: str | None = None


@app.get("/api/watchlist")
def get_watchlist():
    return store.watchlist()


@app.post("/api/watchlist")
def add_watchlist(req: WatchReq):
    try:
        store.add_watch(normalize(req.symbol), req.name, req.grp)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True}


@app.delete("/api/watchlist/{symbol}")
def del_watchlist(symbol: str):
    store.remove_watch(normalize(symbol))
    return {"ok": True}


@app.post("/api/analyze")
def start_analyze(req: AnalyzeReq):
    try:
        norm = normalize(req.symbol)
    except ValueError as e:
        raise HTTPException(400, str(e))
    td = req.trade_date or date.today().isoformat()
    aid = store.new_analysis(norm, td)
    q = _events[aid] = queue.Queue()

    def run():
        store.update_analysis(aid, status="running")
        q.put("running:流水线启动")
        try:
            res = analyze(norm, td,
                          progress_cb=lambda s, d: q.put(f"{s}:{d}"))
            store.update_analysis(
                aid, status="done", decision=res["decision"],
                report_path=res["report_path"],
                finished_at=datetime.now().isoformat(timespec="seconds"))
        except Exception as e:
            logger.exception("分析 %s 失败", norm)
            store.update_analysis(
                aid, status="failed", error=str(e)[:500],
                finished_at=datetime.now().isoformat(timespec="seconds"))
            q.put(f"failed:{str(e)[:200]}")
        q.put(None)

    threading.Thread(target=run, daemon=True).start()
    return {"id": aid, "symbol": norm, "trade_date": td}


@app.get("/api/analyze/{aid}/events")
def analyze_events(aid: int):
    def gen():
        q = _events.get(aid)
        if q is None:  # 进程重启后队列丢失，直接回放最终状态
            rec = store.get_analysis(aid)
            yield f"data: {rec['status'] if rec else 'unknown'}\n\n"
            return
        while True:
            try:
                msg = q.get(timeout=600)
            except queue.Empty:
                yield "data: timeout\n\n"
                break
            if msg is None:
                rec = store.get_analysis(aid)
                yield f"data: final:{rec['status']}\n\n"
                break
            yield f"data: {msg}\n\n"
        _events.pop(aid, None)
    return StreamingResponse(gen(), media_type="text/event-stream")


@app.get("/api/analyses")
def analyses(limit: int = 100):
    return store.list_analyses(limit)


@app.get("/api/report/{aid}")
def report(aid: int):
    rec = store.get_analysis(aid)
    if not rec or not rec["report_path"]:
        raise HTTPException(404, "报告不存在")
    p = Path(rec["report_path"]).resolve()
    reports_root = (Path(ROOT) / "reports").resolve()
    if p.suffix != ".md" or reports_root not in p.parents:
        raise HTTPException(403, "非法路径")
    return PlainTextResponse(p.read_text(encoding="utf-8"))


@app.post("/api/run_daily")
def trigger_daily():
    from ..scheduler import run_daily
    t = threading.Thread(target=run_daily, kwargs={"force": True}, daemon=True)
    t.start()
    return {"ok": True, "msg": "全池分析已在后台启动，结果见分析历史"}


@app.get("/")
def index():
    return FileResponse(Path(__file__).parent / "static" / "index.html")
