#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
环境管理模块 - Python和依赖库的安装与检查
"""

import os
import subprocess
import zipfile
import shutil
from pathlib import Path


class EnvironmentManager:
    """环境管理器"""
    
    def __init__(self, project_dir: Path, log_callback=None):
        self.project_dir = Path(project_dir)
        self.python_dir = self.project_dir / "python"
        self.python_exe = self.python_dir / "python.exe"
        self.libs_dir = self.project_dir / "python_libs"
        self.site_packages = self.libs_dir / "site-packages"
        self.log_callback = log_callback
        
    def log(self, message, level="INFO"):
        """记录日志"""
        if self.log_callback:
            self.log_callback(message, level)
        else:
            print(f"[{level}] {message}")
    
    def is_python_ready(self):
        """检查Python是否已安装"""
        return self.python_exe.exists()
    
    def is_libs_ready(self):
        """检查依赖是否已安装"""
        # 使用绝对路径确保路径正确
        site_packages_abs = self.site_packages.resolve()
        python_exe_abs = self.python_exe.resolve()
        
        if not site_packages_abs.exists():
            return False
        
        env = os.environ.copy()
        env["PYTHONPATH"] = str(site_packages_abs)
        
        try:
            result = subprocess.run(
                [str(python_exe_abs), "-c", 
                 "import flask, pandas, openpyxl, requests, werkzeug"],
                capture_output=True,
                timeout=30,
                env=env
            )
            return result.returncode == 0
        except:
            return False
    
    def check_ollama(self):
        """检查Ollama是否可用（仅检查项目文件夹）"""
        # 只检查项目文件夹中的ollama.exe
        local_ollama = self.project_dir / "ollama" / "ollama.exe"
        if local_ollama.exists():
            try:
                result = subprocess.run(
                    [str(local_ollama), "--version"],
                    capture_output=True,
                    timeout=5
                )
                return result.returncode == 0
            except:
                pass
        
        return False
    
    def check_ollama_zip(self):
        """检查项目文件夹中是否有Ollama压缩包"""
        ollama_dir = self.project_dir / "ollama"
        zip_file = ollama_dir / "ollama-windows-amd64.zip"
        return zip_file.exists()
    
    def install_all(self, progress_callback=None):
        """完整安装环境（仅解压Ollama，Python和依赖已打包）"""
        # 检查Python和依赖是否已存在（由开发者预先安装并打包）
        if not self.is_python_ready():
            self.log("错误: 未找到Python环境，请确保python文件夹已包含在打包中", "ERROR")
            return False
        
        if progress_callback:
            progress_callback(30, "Python已就绪...")
        
        if not self.is_libs_ready():
            self.log("错误: 依赖库未安装，请确保python_libs文件夹已包含在打包中", "ERROR")
            return False
        
        if progress_callback:
            progress_callback(60, "依赖库已就绪...")
        
        # 仅解压Ollama（如果存在压缩包）
        if progress_callback:
            progress_callback(80, "检查Ollama...")
        self._check_and_install_ollama()
        
        if progress_callback:
            progress_callback(100, "安装完成！")
        
        return True
    
    def _check_and_install_ollama(self):
        """解压本地ollama压缩包到项目文件夹"""
        ollama_dir = self.project_dir / "ollama"
        ollama_exe = ollama_dir / "ollama.exe"
        
        # 1. 先检查项目文件夹中是否已有Ollama
        if ollama_exe.exists():
            self.log("Ollama已存在于项目文件夹", "SUCCESS")
            return True
        
        # 2. 查找ollama压缩包
        zip_file = ollama_dir / "ollama-windows-amd64.zip"
        
        if not zip_file.exists():
            self.log("未找到Ollama压缩包", "WARNING")
            self.log(f"请将 ollama-windows-amd64.zip 放入: {ollama_dir}", "INFO")
            return False
        
        self.log("发现Ollama压缩包，开始解压...")
        
        try:
            # 解压到ollama文件夹
            with zipfile.ZipFile(zip_file, 'r') as zf:
                zf.extractall(ollama_dir)
            
            # 处理嵌套文件夹：如果解压后出现了 ollama-windows-amd64/ 子文件夹，移动文件出来
            nested_dir = ollama_dir / "ollama-windows-amd64"
            if nested_dir.exists() and nested_dir.is_dir():
                self.log("检测到嵌套文件夹结构，正在整理...")
                # 移动所有文件到 ollama/ 根目录
                for item in nested_dir.iterdir():
                    target = ollama_dir / item.name
                    if target.exists():
                        if target.is_dir():
                            shutil.rmtree(target)
                        else:
                            target.unlink()
                    shutil.move(str(item), str(target))
                # 删除空文件夹
                nested_dir.rmdir()
                self.log("文件整理完成")
            
            # 验证
            if ollama_exe.exists():
                self.log("Ollama解压成功！", "SUCCESS")
                self.log(f"位置: {ollama_exe}")
                return True
            else:
                self.log("解压后未找到ollama.exe，尝试查找...", "WARNING")
                # 尝试在ollama目录下查找ollama.exe
                for exe_file in ollama_dir.rglob("ollama.exe"):
                    self.log(f"找到ollama.exe: {exe_file}", "INFO")
                    return True
                self.log("未能找到ollama.exe", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"解压Ollama失败: {e}", "ERROR")
            return False
