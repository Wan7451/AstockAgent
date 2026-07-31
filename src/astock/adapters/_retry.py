"""akshare 调用重试封装：东财 push2 域名偶发拒连，统一重试3次。"""
import time
import logging

logger = logging.getLogger(__name__)


def with_retry(fn, *args, retries=3, delay=2.0, **kwargs):
    last = None
    for i in range(retries):
        try:
            return fn(*args, **kwargs)
        except Exception as e:  # noqa: BLE001 网络类异常种类繁多，统一重试
            last = e
            logger.warning("akshare 调用失败(%s/%s): %s %s",
                           i + 1, retries, getattr(fn, "__name__", fn), e)
            time.sleep(delay)
    raise last
