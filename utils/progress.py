# utils/progress.py
# -*- coding: utf-8 -*-
import os
import sys
from typing import Iterable, Iterator, Optional

_USE_TQDM = os.getenv("PROGRESS", "1") != "0"  # 设 PROGRESS=0 可关闭进度条


def _fallback_bar(it: Iterable, total: Optional[int], desc: str) -> Iterator:
    count = 0
    total = int(total) if (total is not None) else None
    prefix = f"{desc} " if desc else ""
    for x in it:
        count += 1
        if total:
            pct = int(count * 100 / total) if total else 0
            sys.stdout.write(f"\r{prefix}{count}/{total} {pct}%")
        else:
            if count % 50 == 0:
                sys.stdout.write(".")
        sys.stdout.flush()
        yield x
    if total:
        sys.stdout.write(f"\r{prefix}{count}/{total} 100%\n")
    else:
        sys.stdout.write("\n")
    sys.stdout.flush()


def pbar(it: Iterable, total: Optional[int] = None, desc: str = "") -> Iterator:
    """
    包装一个可迭代对象，显示进度。
    - 优先用 tqdm（若安装且 PROGRESS!=0）
    - 否则回退到简易文本进度
    """
    if _USE_TQDM:
        try:
            from tqdm import tqdm  # type: ignore
            return tqdm(it, total=total, desc=desc)
        except Exception:
            pass
    return _fallback_bar(it, total, desc)
