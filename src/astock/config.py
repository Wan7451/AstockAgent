"""构建 TradingAgents 运行配置（DeepSeek V4 + akshare 数据源）。"""
import os

from dotenv import load_dotenv
from tradingagents.default_config import DEFAULT_CONFIG

load_dotenv()

# deep_think 不稳时可通过环境变量降级：ASTOCK_DEEP_MODEL=deepseek-v4-flash
DEEP_MODEL = os.getenv("ASTOCK_DEEP_MODEL", "deepseek-v4-pro")
QUICK_MODEL = os.getenv("ASTOCK_QUICK_MODEL", "deepseek-v4-flash")


def build_config() -> dict:
    cfg = dict(DEFAULT_CONFIG)
    cfg.update(
        llm_provider="deepseek",     # base_url 上游 ProviderSpec 内置
        deep_think_llm=DEEP_MODEL,
        quick_think_llm=QUICK_MODEL,
        output_language="zh-CN",
    )
    # 全类目切到 akshare（prediction_markets 保持默认，A股无对应物，
    # 该类目属上游 OPTIONAL_CATEGORIES，不配置不会阻断流程）
    cfg["data_vendors"] = {
        **cfg["data_vendors"],
        **{k: "akshare" for k in cfg["data_vendors"] if k != "prediction_markets"},
    }
    return cfg


def probe_models() -> list[str]:
    """启动时用最小请求探测模型可用性（旧模型名 2026-07-24 已停用的教训）。

    返回不可用模型列表，空列表 = 全部可用。
    """
    from openai import OpenAI
    bad = []
    client = OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"],
                    base_url="https://api.deepseek.com")
    for m in {QUICK_MODEL, DEEP_MODEL}:
        try:
            client.chat.completions.create(
                model=m, max_tokens=1,
                messages=[{"role": "user", "content": "ping"}])
        except Exception as e:
            bad.append(f"{m}: {e}")
    return bad
