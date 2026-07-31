from astock import store


def test_watchlist_crud(tmp_path):
    db = tmp_path / "t.db"
    store.add_watch("600519.SH", "贵州茅台", db_path=db)
    store.add_watch("600519.SH", "重复忽略", db_path=db)
    store.add_watch("000001.SZ", "平安银行", db_path=db)
    wl = store.watchlist(db_path=db)
    assert len(wl) == 2
    assert wl[1]["name"] == "贵州茅台"
    store.remove_watch("600519.SH", db_path=db)
    assert len(store.watchlist(db_path=db)) == 1


def test_analysis_lifecycle(tmp_path):
    db = tmp_path / "t.db"
    aid = store.new_analysis("600519.SH", "2026-07-29", db_path=db)
    store.update_analysis(aid, db_path=db, status="done", decision="HOLD",
                          report_path="reports/x.md")
    rec = store.get_analysis(aid, db_path=db)
    assert rec["status"] == "done" and rec["decision"] == "HOLD"
    assert store.list_analyses(db_path=db)[0]["id"] == aid
