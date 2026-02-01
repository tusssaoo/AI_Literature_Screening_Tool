#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI文献筛选平台 - 智能启动器
入口文件
"""

import sys
from pathlib import Path

# 确保可以导入launcher包
project_dir = Path(__file__).parent
if str(project_dir) not in sys.path:
    sys.path.insert(0, str(project_dir))

from launcher import main

if __name__ == '__main__':
    main()
