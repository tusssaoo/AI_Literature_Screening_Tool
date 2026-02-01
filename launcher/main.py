#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主程序模块 - LauncherApp主类
"""
import os
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path

from .config import Colors, CURRENT_VERSION
from .ui_factory import UIFactory, center_window
from .environment import EnvironmentManager
from .app_controller import AppController
from .update_manager import UpdateManager
from .utils import get_timestamp


class LauncherApp:
    """启动器主应用类"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("AI文献筛选平台 - 智能启动器")
        self.root.geometry("900x800")
        self.root.minsize(850, 700)
        self.root.configure(bg=Colors.LIGHT)
        
        # 窗口居中
        center_window(self.root)
        
        # 项目目录 - 使用当前工作目录的绝对路径
        self.project_dir = Path(os.getcwd()).resolve()
        self.log_file = self.project_dir / "launcher.log"
        
        # 初始化管理器
        self.env_manager = EnvironmentManager(
            self.project_dir, 
            log_callback=self.log
        )
        self.app_controller = AppController(
            self.project_dir,
            self.env_manager.python_exe,
            log_callback=self.log
        )
        self.update_manager = UpdateManager(
            self.project_dir,
            CURRENT_VERSION,
            log_callback=self.log,
            progress_callback=self.update_progress,
            status_callback=self._on_update_status_change
        )
        
        # UI工厂
        self.ui_factory = UIFactory(self.root)
        self.ui_factory.setup_styles()
        
        # 状态变量
        self.is_installing = False
        self.status_vars = {"python": tk.StringVar(value="检测中..."),
                           "libs": tk.StringVar(value="检测中..."),
                           "ollama": tk.StringVar(value="检测中...")}
        
        # 创建UI
        self._create_ui()
        
        # 启动时检查
        self.root.after(500, self._initial_check)
    
    def _create_ui(self):
        """创建UI界面"""
        main_container = tk.Frame(self.root, bg=Colors.LIGHT)
        main_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        self._create_header(main_container)
        self._create_status_cards(main_container)
        self._create_progress_section(main_container)
        self._create_button_section(main_container)
        self._create_log_section(main_container)
        self._create_footer(main_container)
    
    def _create_header(self, parent):
        """创建标题"""
        header = tk.Frame(parent, bg=Colors.DARK, height=100)
        header.pack(fill=tk.X, pady=(0, 20))
        header.pack_propagate(False)
        
        title_frame = tk.Frame(header, bg=Colors.DARK)
        title_frame.pack(expand=True)
        
        tk.Label(title_frame, text="📚", font=("Segoe UI Emoji", 40),
                bg=Colors.DARK).pack(side=tk.LEFT, padx=(0, 15))
        
        text_frame = tk.Frame(title_frame, bg=Colors.DARK)
        text_frame.pack(side=tk.LEFT)
        
        tk.Label(text_frame, text="AI文献筛选平台",
                font=("Microsoft YaHei", 24, "bold"),
                fg="white", bg=Colors.DARK).pack(anchor="w")
        
        tk.Label(text_frame, text="智能文献筛选与分析工具",
                font=("Microsoft YaHei", 11),
                fg="#bdc3c7", bg=Colors.DARK).pack(anchor="w")
    
    def _create_status_cards(self, parent):
        """创建状态卡片"""
        cards_frame = tk.Frame(parent, bg=Colors.LIGHT)
        cards_frame.pack(fill=tk.X, pady=(0, 15))
        
        statuses = [
            ("python", "Python环境", "🐍", Colors.PRIMARY),
            ("libs", "依赖库", "📦", Colors.SUCCESS),
            ("ollama", "Ollama服务", "🤖", Colors.WARNING)
        ]
        
        for i, (key, title, icon, color) in enumerate(statuses):
            card = tk.Frame(cards_frame, bg="white", bd=1, relief=tk.SOLID)
            card.grid(row=0, column=i, padx=10, pady=5, sticky="nsew")
            cards_frame.grid_columnconfigure(i, weight=1)
            
            tk.Label(card, text=icon, font=("Segoe UI Emoji", 32),
                    bg="white", fg=color).pack(pady=(15, 5))
            tk.Label(card, text=title, font=("Microsoft YaHei", 11, "bold"),
                    bg="white", fg=Colors.DARK).pack()
            tk.Label(card, textvariable=self.status_vars[key],
                    font=("Microsoft YaHei", 10),
                    bg="white", fg=Colors.GRAY).pack(pady=(5, 15))
    
    def _create_progress_section(self, parent):
        """创建进度条区域"""
        self.progress_frame = tk.LabelFrame(parent, text="安装进度",
                                           font=("Microsoft YaHei", 10, "bold"),
                                           bg=Colors.LIGHT, fg=Colors.DARK)
        self.progress_frame.pack(fill=tk.X, pady=(0, 15))
        self.progress_frame.pack_forget()
        
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(self.progress_frame,
                                           variable=self.progress_var,
                                           maximum=100, mode='determinate',
                                           length=400)
        self.progress_bar.pack(fill=tk.X, padx=10, pady=10)
        
        self.progress_text = tk.Label(self.progress_frame, text="",
                                     font=("Microsoft YaHei", 9),
                                     bg=Colors.LIGHT, fg=Colors.GRAY)
        self.progress_text.pack(pady=(0, 10))
    
    def _create_button_section(self, parent):
        """创建按钮区域"""
        btn_frame = tk.Frame(parent, bg=Colors.LIGHT)
        btn_frame.pack(fill=tk.X, pady=(0, 15))
        
        # 主按钮
        self.main_btn = UIFactory.create_button(
            btn_frame, "🚀 启动应用", self.on_start,
            bg_color=Colors.SUCCESS, width=20, font_size=12
        )
        self.main_btn.pack(pady=10)
        
        # 辅助按钮
        sub_btn_frame = tk.Frame(btn_frame, bg=Colors.LIGHT)
        sub_btn_frame.pack()
        
        self.install_btn = UIFactory.create_button(
            sub_btn_frame, "📦 安装环境", self.on_install,
            bg_color=Colors.PRIMARY, width=15
        )
        self.install_btn.pack(side=tk.LEFT, padx=5)
        
        self.stop_btn = UIFactory.create_button(
            sub_btn_frame, "⏹ 停止应用", self.on_stop,
            bg_color=Colors.DANGER, width=15
        )
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        self.stop_btn.config(state=tk.DISABLED)
        
        self.reinstall_btn = UIFactory.create_button(
            sub_btn_frame, "🔄 重新安装", self.on_reinstall,
            bg_color=Colors.GRAY, width=15
        )
        self.reinstall_btn.pack(side=tk.LEFT, padx=5)
        
        self.update_btn = UIFactory.create_button(
            sub_btn_frame, "⬆️ 检查更新", self.on_check_update,
            bg_color=Colors.WARNING, width=15
        )
        self.update_btn.pack(side=tk.LEFT, padx=5)
    
    def _create_log_section(self, parent):
        """创建日志区域"""
        log_frame = tk.LabelFrame(parent, text="运行日志",
                                 font=("Microsoft YaHei", 10, "bold"),
                                 bg=Colors.LIGHT, fg=Colors.DARK)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        self.log_text = tk.Text(log_frame, height=15,
                               font=("Consolas", 10),
                               bg="white", fg=Colors.DARK,
                               padx=10, pady=10, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        scrollbar = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=scrollbar.set)
    
    def _create_footer(self, parent):
        """创建底部信息"""
        footer = tk.Frame(parent, bg=Colors.LIGHT)
        footer.pack(fill=tk.X)
        
        tk.Label(footer, text=f"版本: v{CURRENT_VERSION}",
                font=("Microsoft YaHei", 9),
                fg=Colors.GRAY, bg=Colors.LIGHT).pack(side=tk.LEFT)
        
        tk.Label(footer, text="Made with ❤️ for Researchers",
                font=("Microsoft YaHei", 9),
                fg=Colors.GRAY, bg=Colors.LIGHT).pack(side=tk.RIGHT)
    
    def log(self, message, level="INFO"):
        """记录日志"""
        timestamp = get_timestamp()
        
        self.log_text.insert(tk.END, f"[{timestamp}] ", "timestamp")
        self.log_text.insert(tk.END, f"[{level}] ", level)
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)
        
        # 写入文件
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(f"[{timestamp}] [{level}] {message}\n")
    
    def update_progress(self, value, text=""):
        """更新进度条"""
        self.progress_var.set(value)
        if text:
            self.progress_text.config(text=text)
        self.root.update_idletasks()
    
    def show_progress(self, show=True):
        """显示/隐藏进度条"""
        if show:
            self.progress_frame.pack(fill=tk.X, pady=(0, 15),
                                    before=self.main_btn.master)
        else:
            self.progress_frame.pack_forget()
    
    def _initial_check(self):
        """启动时检查环境"""
        self.log("=" * 60)
        self.log("启动器初始化...")
        self.log("=" * 60)
        
        # Python
        if self.env_manager.is_python_ready():
            self.status_vars["python"].set("已安装 ✓")
            self.log("Python环境已就绪", "SUCCESS")
        else:
            self.status_vars["python"].set("未安装 ✗")
            self.log("Python环境未安装", "WARNING")
        
        # 依赖
        if self.env_manager.is_libs_ready():
            self.status_vars["libs"].set("已安装 ✓")
            self.log("依赖库已就绪", "SUCCESS")
        else:
            self.status_vars["libs"].set("未安装 ✗")
            self.log("依赖库未安装", "WARNING")
        
        # Ollama
        if self.env_manager.check_ollama():
            self.status_vars["ollama"].set("已安装 ✓")
            self.log("Ollama服务已就绪", "SUCCESS")
        elif self.env_manager.check_ollama_zip():
            self.status_vars["ollama"].set("待解压 📦")
            self.log("检测到Ollama压缩包，请在安装时解压", "INFO")
        else:
            self.status_vars["ollama"].set("未安装 ⚠")
            self.log("Ollama未安装（可选）", "WARNING")
        
        self._update_button_state()
    
    def _update_button_state(self):
        """更新按钮状态"""
        python_ready = self.env_manager.is_python_ready()
        libs_ready = self.env_manager.is_libs_ready()
        running = self.app_controller.is_running
        
        if running:
            self.main_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.NORMAL)
            self.install_btn.config(state=tk.DISABLED)
            self.reinstall_btn.config(state=tk.DISABLED)
        else:
            self.stop_btn.config(state=tk.DISABLED)
            if python_ready and libs_ready:
                self.main_btn.config(state=tk.NORMAL)
                self.install_btn.config(state=tk.NORMAL)
                self.reinstall_btn.config(state=tk.NORMAL)
            else:
                self.main_btn.config(state=tk.DISABLED)
                self.install_btn.config(state=tk.NORMAL)
                self.reinstall_btn.config(state=tk.DISABLED)
    
    def _on_update_status_change(self, status):
        """更新状态变更回调"""
        if status == "updating":
            self.update_btn.config(state=tk.DISABLED, text="⬇️ 更新中...")
            self.show_progress(True)
        else:
            self.update_btn.config(state=tk.NORMAL, text="⬆️ 检查更新")
            self.show_progress(False)
    
    def on_start(self):
        """启动应用"""
        self.log("\n" + "=" * 60)
        self.log("启动应用...", "COMMAND")
        
        # 检查项目文件夹中的Ollama是否存在
        if not self.env_manager.check_ollama():
            if self.env_manager.check_ollama_zip():
                self.log("检测到Ollama压缩包，请先安装环境以解压", "WARNING")
                self.log("点击【安装环境】按钮解压Ollama", "INFO")
            else:
                self.log("未检测到Ollama，请确保项目文件夹中有ollama/ollama.exe", "WARNING")
                self.log("或点击【安装环境】进行完整安装", "INFO")
            return
        
        def on_started(success):
            self._update_button_state()
            if success:
                self.log("应用启动成功！", "SUCCESS")
            else:
                self.log("应用启动可能失败，请检查日志", "WARNING")
        
        if self.app_controller.start(callback=on_started):
            self._update_button_state()
    
    def on_stop(self):
        """停止应用"""
        self.log("\n" + "=" * 60)
        self.log("停止应用...", "COMMAND")
        
        if self.app_controller.stop():
            self._update_button_state()
    
    def on_install(self):
        """安装环境"""
        if self.is_installing:
            return
        
        self.is_installing = True
        self.show_progress(True)
        self.update_progress(0, "准备安装...")
        
        def install_thread():
            try:
                success = self.env_manager.install_all(
                    progress_callback=self.update_progress
                )
                
                if success:
                    self.log("\n环境安装完成！", "SUCCESS")
                    messagebox.showinfo("完成", "环境安装完成！")
                else:
                    self.log("\n环境安装失败", "ERROR")
                    messagebox.showerror("错误", "环境安装失败，请查看日志")
                    
            except Exception as e:
                self.log(f"安装出错: {e}", "ERROR")
                messagebox.showerror("错误", f"安装失败: {e}")
            finally:
                self.is_installing = False
                self.root.after(0, lambda: self.show_progress(False))
                self.root.after(0, self._initial_check)
        
        threading.Thread(target=install_thread, daemon=True).start()
    
    def on_reinstall(self):
        """重新安装"""
        if messagebox.askyesno("确认", "确定要重新安装环境吗？\n这会清除现有环境并重新安装。"):
            # 清理现有环境
            self.log("清理现有环境...")
            import shutil
            if self.env_manager.python_dir.exists():
                shutil.rmtree(self.env_manager.python_dir, ignore_errors=True)
            if self.env_manager.libs_dir.exists():
                shutil.rmtree(self.env_manager.libs_dir, ignore_errors=True)
            
            self.log("环境已清理，开始重新安装...")
            self.on_install()
    
    def on_check_update(self):
        """检查更新"""
        dialog = tk.Toplevel(self.root)
        dialog.title("检查更新")
        dialog.geometry("400x300")
        dialog.configure(bg=Colors.LIGHT)
        dialog.transient(self.root)
        dialog.grab_set()
        
        tk.Label(dialog, text="⬆️ 软件更新",
                font=("Microsoft YaHei", 16, "bold"),
                fg=Colors.DARK, bg=Colors.LIGHT).pack(pady=(20, 10))
        
        tk.Label(dialog, text=f"当前版本: v{CURRENT_VERSION}",
                font=("Microsoft YaHei", 10),
                fg=Colors.GRAY, bg=Colors.LIGHT).pack(pady=(0, 20))
        
        btn_frame = tk.Frame(dialog, bg=Colors.LIGHT)
        btn_frame.pack(pady=10)
        
        tk.Button(btn_frame, text="📁 本地更新",
                 font=("Microsoft YaHei", 11),
                 bg=Colors.SUCCESS, fg="white",
                 width=15, height=2,
                 command=lambda: self._do_local_update(dialog),
                 relief=tk.FLAT).pack(side=tk.LEFT, padx=10)
        
        tk.Button(btn_frame, text="🌐 联网更新",
                 font=("Microsoft YaHei", 11),
                 bg=Colors.PRIMARY, fg="white",
                 width=15, height=2,
                 command=lambda: messagebox.showinfo("联网更新",
                     "🚧 联网更新功能暂不支持\n\n请使用本地更新方式。"),
                 relief=tk.FLAT).pack(side=tk.LEFT, padx=10)
        
        tk.Button(dialog, text="取消",
                 font=("Microsoft YaHei", 10),
                 bg=Colors.GRAY, fg="white",
                 width=10,
                 command=dialog.destroy,
                 relief=tk.FLAT).pack(pady=15)
        
        tk.Label(dialog, text="提示: 本地更新需要选择 package.bat 打包的 ZIP 压缩包",
                font=("Microsoft YaHei", 9),
                fg=Colors.GRAY, bg=Colors.LIGHT).pack(pady=(5, 0))
    
    def _do_local_update(self, dialog):
        """执行本地更新"""
        dialog.destroy()
        
        def on_complete(success):
            if success:
                messagebox.showinfo("更新完成",
                    "更新已成功安装！\n\n请重启启动器以使用新版本。")
                self.root.quit()
        
        self.update_manager.select_and_update(on_complete=on_complete)


def main():
    """主函数"""
    root = tk.Tk()
    LauncherApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
