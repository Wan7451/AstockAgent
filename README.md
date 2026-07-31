# A股多智能体投研决策系统

基于 [TradingAgents](https://github.com/TauricResearch/TradingAgents) 多智能体框架 + akshare A股数据源的投研决策支持系统。每日自动分析自选股池，也支持按需分析任意 A股，输出结构化研究报告（技术面/情绪面/新闻面/基本面 → 多空辩论 → 交易员方案 → 风控终审）。

> ⚠️ 本系统仅输出研究参考，不构成投资建议，不接入任何交易通道，交易决策由使用者人工执行。

## 架构

```
┌─ Web (FastAPI + SSE) ── 自选股池 / 按需分析 / 报告查看
├─ Scheduler (APScheduler) ── 交易日 15:30 自动跑全池
├─ Pipeline ── TradingAgentsGraph.propagate() → Markdown 报告
├─ Adapters（本项目核心，src/astock/adapters/）
│    akshare 实现 10 个 vendor 方法，运行时注入上游 VENDOR_METHODS
│    多源降级：东方财富 → 新浪 / 雪球 / 财联社
├─ Analysis（src/astock/analysis/）
│    结构分析：缠论（本地算法）+ 威科夫（特征算法+LLM判定），周/日/30分钟三级别联立
│    报告独立两章节，摘要注入市场分析师数据流参与主决策
└─ vendor/TradingAgents ── 上游框架（git submodule，源码零修改）
```

- **上游零修改**：所有 A股适配通过 `registry.register()` 运行时注入（vendor 路由表 + `load_ohlcv` 补丁），升级上游后运行 `scripts/smoke_upstream.py` 验证兼容性。
- **LLM**：DeepSeek（deep=`deepseek-v4-pro`，quick=`deepseek-v4-flash`），可用环境变量 `ASTOCK_DEEP_MODEL` / `ASTOCK_QUICK_MODEL` 覆盖。
- **防前视**：新闻按分析日期窗口过滤；日K补丁按 curr_date 截断。

## 安装

```bash
git clone --recurse-submodules <repo-url> astock-agent && cd astock-agent
python3 -m venv .venv && source .venv/bin/activate
pip install -e vendor/TradingAgents
pip install akshare fastapi "uvicorn[standard]" apscheduler pytest python-dotenv stockstats
cp .env.example .env   # 填入 DEEPSEEK_API_KEY
```

## 使用

```bash
# Web 界面（含每日调度器）
.venv/bin/uvicorn astock.web.app:app --app-dir src --port 8620
# 打开 http://127.0.0.1:8620

# 命令行：单只股票
.venv/bin/python -c "import sys; sys.path.insert(0,'src'); from astock.pipeline import analyze; print(analyze('600519'))"

# 命令行：手动跑一遍全池（生成 daily_summary.md）
.venv/bin/python scripts/run_daily.py --force
```

报告输出在 `reports/<日期>/<代码>.md`，自选股与分析历史存于 `data/astock.db`（SQLite）。

## 测试

```bash
.venv/bin/python -m pytest tests/ -q      # 单元测试（全部离线 mock）
.venv/bin/python scripts/smoke_upstream.py  # 上游兼容性冒烟（升级 submodule 后必跑）
```

## 目录

| 路径 | 说明 |
|---|---|
| `src/astock/adapters/` | akshare 数据适配层（symbols/market_data/fundamentals/news/macro/insider/registry） |
| `src/astock/config.py` | 上游配置构建 + 模型可用性探测 |
| `src/astock/pipeline.py` | 单股分析流水线 → Markdown 报告 |
| `src/astock/store.py` / `scheduler.py` | SQLite 存储 / 每日定时任务 |
| `src/astock/web/` | FastAPI 后端 + 单页前端 |
| `vendor/TradingAgents` | 上游框架 submodule（锁定 commit 见 `vendor/UPSTREAM_COMMIT`） |

## 已知数据源状态

东方财富实时接口（push2 域名）在部分网络下不稳定，系统自动降级：日K→新浪、公司概况→雪球；财务三表（push2his 域名）与新浪财务指标正常。所有降级路径均有日志告警，不阻断流水线。
