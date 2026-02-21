#!/usr/bin/env python3
"""文旅数据研究工具 — 入口"""

import sys
from pathlib import Path

# 确保 src/ 可被导入
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.cli import main

if __name__ == "__main__":
    main()
