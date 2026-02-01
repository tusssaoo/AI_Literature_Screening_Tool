#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工具函数模块
"""

import socket
import re
from pathlib import Path
from datetime import datetime


def find_free_port(start_port=5001, max_port=5100):
    """查找可用端口"""
    for port in range(start_port, max_port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('127.0.0.1', port))
                return port
            except OSError:
                continue
    return None


def compare_version(v1, v2):
    """比较版本号，返回 1(v1>v2), 0(相等), -1(v1<v2)"""
    def parse_version(v):
        # 提取数字部分
        numbers = re.findall(r'\d+', str(v))
        return [int(n) for n in numbers] if numbers else [0]
    
    v1_parts = parse_version(v1)
    v2_parts = parse_version(v2)
    
    # 补齐长度
    max_len = max(len(v1_parts), len(v2_parts))
    v1_parts.extend([0] * (max_len - len(v1_parts)))
    v2_parts.extend([0] * (max_len - len(v2_parts)))
    
    for i in range(max_len):
        if v1_parts[i] > v2_parts[i]:
            return 1
        elif v1_parts[i] < v2_parts[i]:
            return -1
    return 0


def read_version_from_launcher(launcher_file: Path):
    """从launcher.py文件读取版本号"""
    version_info = {"version": "未知", "changelog": "无更新说明"}
    
    try:
        if launcher_file.exists():
            content = launcher_file.read_text(encoding='utf-8')
            match = re.search(r'self\.current_version\s*=\s*"([^"]+)"', content)
            if match:
                version_info["version"] = match.group(1)
            # 尝试读取changelog
            match_log = re.search(r'__version__\s*=\s*"[^"]+"\s*\n\s*"""(.*?)"""', content, re.DOTALL)
            if match_log:
                version_info["changelog"] = match_log.group(1).strip()
    except:
        pass
    
    return version_info


def get_timestamp():
    """获取当前时间戳字符串"""
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
