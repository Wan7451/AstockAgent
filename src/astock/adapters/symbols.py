"""A股代码格式互转。内部规范格式：'600519.SH'。

规则（借鉴 ValueCell akshare_adapter 的判别逻辑，仅保留 A股分支）：
6 开头→上交所 SH；0/2/3 开头→深交所 SZ；4/8/9 开头→北交所 BJ。
"""
import re

_SUFFIX_MAP = {"SS": "SH", "SH": "SH", "SZ": "SZ", "BJ": "BJ"}

def normalize(raw: str) -> str:
    s = str(raw).strip().upper()
    m = re.fullmatch(r"(?:(SH|SZ|BJ)\.?)?(\d{6})(?:\.(SS|SH|SZ|BJ))?", s)
    if not m:
        raise ValueError(f"无法识别的A股代码: {raw!r}")
    prefix, code, suffix = m.groups()
    exch = _SUFFIX_MAP.get(suffix or "") or prefix or _infer_exchange(code)
    return f"{code}.{exch}"

def _infer_exchange(code: str) -> str:
    if code[0] == "6":
        return "SH"
    if code[0] in "023":
        return "SZ"
    if code[0] in "489":
        return "BJ"
    raise ValueError(f"无法推断交易所: {code}")

def to_akshare(norm: str) -> str:
    """akshare 多数 A股接口用纯 6 位数字。"""
    return norm.split(".")[0]

def to_em_prefixed(norm: str) -> str:
    """东财财务报表接口用 SH600519 形式。"""
    code, exch = norm.split(".")
    return f"{exch}{code}"

def exchange_of(norm: str) -> str:
    return norm.split(".")[1]
