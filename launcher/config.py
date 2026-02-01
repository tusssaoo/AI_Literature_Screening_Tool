#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置文件 - 常量、颜色、版本信息
"""

class Colors:
    """颜色配置"""
    PRIMARY = "#3498db"
    SUCCESS = "#27ae60"
    WARNING = "#f39c12"
    DANGER = "#e74c3c"
    DARK = "#2c3e50"
    LIGHT = "#ecf0f1"
    GRAY = "#95a5a6"


# 版本信息
CURRENT_VERSION = "1.0.0"
UPDATE_URL = ""  # 设置为您的更新服务器地址

# 文件列表
REQUIRED_FILES = ["run_launcher.py", "app.py"]
UPDATE_FILES = [
    "launcher.py", "app.py", "requirements.txt",
    "start_launcher.bat", "README.md"
]

# Python下载地址
PYTHON_URL = "https://www.python.org/ftp/python/3.11.8/python-3.11.8-embed-amd64.zip"
PIP_URL = "https://bootstrap.pypa.io/get-pip.py"

# 镜像源
PYPI_MIRROR = "https://pypi.tuna.tsinghua.edu.cn/simple"
