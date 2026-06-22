"""
StarVoyage AI Video Engine — 项目入口
=======================================
将 vendor/ 目录加入 sys.path，使 ShortGPT、OpenMontage 等本地依赖可导入。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

__version__ = "0.1.0"

# ── Vendor path setup ──────────────────────────────────────────────────────
# 将项目根目录下的 vendor/ 加入 Python 模块搜索路径。
# 这样 ShortGPT、OpenMontage 克隆到 vendor/ 后就能直接 import，
# 无需 pip install 到全局 site-packages。
_VENDOR_DIR = Path(__file__).resolve().parent.parent / "vendor"

if _VENDOR_DIR.is_dir():
    # 将 vendor 子目录（ShortGPT/OpenMontage 等）加入 sys.path
    for _p in sorted(_VENDOR_DIR.iterdir()):
        _item = _VENDOR_DIR / _p
        if _item.is_dir() and not _item.name.startswith("."):
            _str = str(_item.resolve())
            if _str not in sys.path:
                sys.path.insert(0, _str)

    # vendor 根目录本身也加入，方便 vendor/xxx.py 形式的导入
    _str = str(_VENDOR_DIR.resolve())
    if _str not in sys.path:
        sys.path.insert(0, _str)

    del _p, _item, _str

del os, Path
