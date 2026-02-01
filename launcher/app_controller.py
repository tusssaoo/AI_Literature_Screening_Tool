#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
应用控制器模块 - 启动、停止应用服务
"""

import os
import sys
import subprocess
import time
import webbrowser
import threading
from pathlib import Path
from .utils import find_free_port


class AppController:
    """应用控制器"""
    
    def __init__(self, project_dir: Path, python_exe: Path, log_callback=None):
        self.project_dir = Path(project_dir)
        self.python_exe = Path(python_exe)
        self.log_callback = log_callback
        self.server_process = None
        self.ollama_process = None
        self.is_running = False
        self.port = None
        
    def log(self, message, level="INFO"):
        """记录日志"""
        if self.log_callback:
            self.log_callback(message, level)
        else:
            print(f"[{level}] {message}")
    
    def start(self, callback=None):
        """启动应用"""
        if self.is_running:
            self.log("应用已经在运行中", "WARNING")
            return False
        
        # 查找可用端口
        self.port = find_free_port()
        if not self.port:
            self.log("错误: 无法找到可用端口", "ERROR")
            return False
        
        self.log(f"使用端口: {self.port}")
        
        # 准备环境
        env = os.environ.copy()
        site_packages = self.project_dir / "python_libs" / "site-packages"
        env["PYTHONPATH"] = str(site_packages)
        env["FLASK_PORT"] = str(self.port)
        # 设置项目目录环境变量，供app.py使用（使用绝对路径）
        project_dir_abs = str(self.project_dir.resolve())
        env["PROJECT_DIR"] = project_dir_abs
        
        # 设置Ollama模型路径（如果项目中有ollama文件夹）
        ollama_models_dir = self.project_dir / "ollama" / "models"
        if ollama_models_dir.exists():
            env["OLLAMA_MODELS"] = str(ollama_models_dir.resolve())
        
        # 设置 Ollama API 地址
        env["OLLAMA_HOST"] = "http://localhost:11434"
        
        # 如果项目文件夹中有ollama，将其添加到PATH最前面，并启动Ollama服务
        local_ollama_dir = self.project_dir / "ollama"
        ollama_exe = local_ollama_dir / "ollama.exe"
        
        if ollama_exe.exists():
            current_path = env.get("PATH", "")
            env["PATH"] = str(local_ollama_dir) + os.pathsep + current_path
            self.log(f"使用项目内置Ollama: {local_ollama_dir}")
            
            # 设置Ollama模型存储路径为项目文件夹
            ollama_models_dir = local_ollama_dir / "models"
            ollama_models_dir.mkdir(parents=True, exist_ok=True)
            env["OLLAMA_MODELS"] = str(ollama_models_dir)
            self.log(f"模型将存储到: {ollama_models_dir}")
            
            # 先终止可能正在运行的Ollama进程，确保环境变量生效
            self._kill_existing_ollama()
            
            # 启动Ollama服务
            try:
                self.log("正在启动Ollama服务...")
                self.ollama_process = subprocess.Popen(
                    [str(ollama_exe), "serve"],
                    cwd=str(local_ollama_dir),
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
                )
                self.log("Ollama服务启动中，等待初始化...")
                time.sleep(5)  # 增加等待时间到5秒
                
                # 检查 Ollama 是否真的在监听
                import socket
                ollama_running = False
                for _ in range(10):  # 尝试10次
                    try:
                        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sock.settimeout(1)
                        result = sock.connect_ex(('127.0.0.1', 11434))
                        sock.close()
                        if result == 0:
                            ollama_running = True
                            break
                    except:
                        pass
                    time.sleep(0.5)
                
                if ollama_running:
                    self.log("Ollama服务已成功启动 (端口11434)", "SUCCESS")
                    # 检查已安装的模型
                    try:
                        import urllib.request
                        import json
                        req = urllib.request.Request('http://127.0.0.1:11434/api/tags')
                        with urllib.request.urlopen(req, timeout=5) as response:
                            data = json.loads(response.read().decode())
                            models = [m['name'] for m in data.get('models', [])]
                            if models:
                                self.log(f"已安装模型: {', '.join(models)}")
                            else:
                                self.log("尚未安装任何模型", "WARNING")
                    except Exception as e:
                        self.log(f"无法获取模型列表: {e}", "WARNING")
                else:
                    self.log("警告: Ollama服务可能未正常启动，请检查", "WARNING")
            except Exception as e:
                self.log(f"启动Ollama服务失败: {e}", "WARNING")
        
        try:
            # 启动Flask应用
            self.server_process = subprocess.Popen(
                [str(self.python_exe), "app.py"],
                cwd=str(self.project_dir),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            
            self.is_running = True
            self.log("应用启动中...", "SUCCESS")
            
            # 后台线程监控输出
            threading.Thread(target=self._monitor_output, daemon=True).start()
            
            # 等待服务启动
            threading.Thread(target=self._wait_and_open, args=(callback,), daemon=True).start()
            
            return True
            
        except Exception as e:
            self.log(f"启动失败: {e}", "ERROR")
            self.is_running = False
            return False
    
    def stop(self):
        """停止应用"""
        if not self.is_running or not self.server_process:
            self.log("应用未在运行", "WARNING")
            return False
        
        try:
            # 停止Flask应用
            self.server_process.terminate()
            try:
                self.server_process.wait(timeout=5)
            except:
                self.server_process.kill()
            
            self.server_process = None
            
            # 停止Ollama服务
            if self.ollama_process:
                try:
                    self.ollama_process.terminate()
                    try:
                        self.ollama_process.wait(timeout=5)
                    except:
                        self.ollama_process.kill()
                    self.log("Ollama服务已停止", "INFO")
                except Exception as e:
                    self.log(f"停止Ollama服务时出错: {e}", "WARNING")
                self.ollama_process = None
            
            self.is_running = False
            self.log("应用已停止", "SUCCESS")
            return True
            
        except Exception as e:
            self.log(f"停止应用时出错: {e}", "ERROR")
            return False
    
    def _monitor_output(self):
        """监控应用输出"""
        if not self.server_process:
            return
        
        def read_stream(stream, prefix):
            try:
                while self.is_running and self.server_process:
                    line = stream.readline()
                    if line:
                        decoded = line.decode('utf-8', errors='ignore').strip()
                        if decoded:
                            self.log(f"[{prefix}] {decoded}")
                    else:
                        break
            except:
                pass
        
        # 同时监控stdout和stderr
        import threading
        stdout_thread = threading.Thread(target=read_stream, args=(self.server_process.stdout, "App"), daemon=True)
        stderr_thread = threading.Thread(target=read_stream, args=(self.server_process.stderr, "AppERR"), daemon=True)
        stdout_thread.start()
        stderr_thread.start()
    
    def _wait_and_open(self, callback=None):
        """等待服务启动并打开浏览器"""
        import socket
        
        max_attempts = 30
        for _ in range(max_attempts):
            time.sleep(1)
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(2)
                    result = s.connect_ex(('127.0.0.1', self.port))
                    if result == 0:
                        self.log(f"服务已启动: http://127.0.0.1:{self.port}", "SUCCESS")
                        webbrowser.open(f"http://127.0.0.1:{self.port}")
                        if callback:
                            callback(True)
                        return
            except:
                pass
        
        self.log("服务启动超时，请手动检查", "WARNING")
        if callback:
            callback(False)
    
    def get_status(self):
        """获取运行状态"""
        if self.is_running and self.server_process:
            # 检查进程是否还在运行
            if self.server_process.poll() is None:
                return True, self.port
            else:
                self.is_running = False
                return False, None
        return False, None
    
    def _kill_existing_ollama(self):
        """终止现有的Ollama进程，确保环境变量生效"""
        try:
            if sys.platform == 'win32':
                # Windows: 使用taskkill终止ollama.exe进程
                result = subprocess.run(
                    ['taskkill', '/F', '/IM', 'ollama.exe', '/T'],
                    capture_output=True,
                    timeout=10
                )
                if result.returncode == 0:
                    self.log("已终止现有Ollama进程")
                    time.sleep(2)  # 等待进程完全终止
            else:
                # Linux/Mac: 使用pkill
                result = subprocess.run(
                    ['pkill', '-f', 'ollama'],
                    capture_output=True,
                    timeout=10
                )
                if result.returncode == 0:
                    self.log("已终止现有Ollama进程")
                    time.sleep(2)
        except Exception:
            # 如果没有运行中的进程，会报错，忽略
            pass
