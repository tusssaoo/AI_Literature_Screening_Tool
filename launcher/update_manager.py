#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
更新管理模块 - 本地更新和版本管理
"""

import shutil
import zipfile
import tempfile
import threading
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox
from .config import UPDATE_FILES, REQUIRED_FILES
from .utils import compare_version, read_version_from_launcher


class UpdateManager:
    """更新管理器"""
    
    def __init__(self, project_dir: Path, current_version, log_callback=None, 
                 progress_callback=None, status_callback=None):
        self.project_dir = Path(project_dir)
        self.current_version = current_version
        self.log_callback = log_callback
        self.progress_callback = progress_callback
        self.status_callback = status_callback
        self.is_updating = False
        
    def log(self, message, level="INFO"):
        if self.log_callback:
            self.log_callback(message, level)
        else:
            print(f"[{level}] {message}")
    
    def select_and_update(self, on_complete=None):
        """选择zip文件并执行更新"""
        # 选择zip文件
        zip_path = filedialog.askopenfilename(
            title="选择新版本压缩包 (AI_Literature_Screening_v*.zip)",
            filetypes=[("ZIP压缩包", "*.zip"), ("所有文件", "*.*")],
            defaultextension=".zip"
        )
        
        if not zip_path:
            return False
        
        selected_zip = Path(zip_path)
        
        if not selected_zip.exists():
            messagebox.showerror("错误", "选择的文件不存在！")
            return False
        
        if not selected_zip.suffix.lower() == '.zip':
            messagebox.showerror("错误", "请选择 .zip 格式的压缩包文件！")
            return False
        
        # 解压到临时目录
        temp_dir = tempfile.mkdtemp(prefix="ai_update_")
        extract_path = Path(temp_dir) / "extracted"
        
        try:
            self.log(f"正在解压更新包: {selected_zip.name}")
            with zipfile.ZipFile(selected_zip, 'r') as zf:
                zf.extractall(extract_path)
            
            # 查找项目根目录
            source_path = self._find_project_root(extract_path)
            if not source_path:
                messagebox.showerror("无效的压缩包", 
                    "压缩包中未找到有效的项目文件！")
                shutil.rmtree(temp_dir, ignore_errors=True)
                return False
            
            # 验证
            if not self._validate_source(source_path):
                shutil.rmtree(temp_dir, ignore_errors=True)
                return False
            
            # 读取版本
            version_info = read_version_from_launcher(source_path / "launcher.py")
            new_version = version_info.get("version", "未知")
            
            # 确认更新
            if not self._confirm_update(new_version):
                shutil.rmtree(temp_dir, ignore_errors=True)
                return False
            
            # 开始更新
            self.is_updating = True
            if self.status_callback:
                self.status_callback("updating")
            
            threading.Thread(target=self._apply_update, 
                           args=(source_path, temp_dir, on_complete), 
                           daemon=True).start()
            
            return True
            
        except zipfile.BadZipFile:
            messagebox.showerror("错误", "无效的zip文件！")
            shutil.rmtree(temp_dir, ignore_errors=True)
            return False
        except Exception as e:
            messagebox.showerror("错误", f"解压失败: {str(e)}")
            shutil.rmtree(temp_dir, ignore_errors=True)
            return False
    
    def _find_project_root(self, extract_path):
        """在解压目录中查找项目根目录"""
        if (extract_path / "launcher.py").exists() and (extract_path / "app.py").exists():
            return extract_path
        
        for subdir in extract_path.iterdir():
            if subdir.is_dir():
                if (subdir / "launcher.py").exists() and (subdir / "app.py").exists():
                    return subdir
        return None
    
    def _validate_source(self, source_path):
        """验证更新源是否有效"""
        missing_files = []
        
        for file_name in REQUIRED_FILES:
            if not (source_path / file_name).exists():
                missing_files.append(file_name)
        
        if missing_files:
            messagebox.showerror("无效的文件夹", 
                f"缺少必要的文件:\n" + "\n".join(missing_files))
            return False
        
        if source_path.resolve() == self.project_dir.resolve():
            messagebox.showerror("错误", "不能选择当前项目文件夹作为更新源！")
            return False
        
        return True
    
    def _confirm_update(self, new_version):
        """确认更新"""
        comparison = compare_version(new_version, self.current_version)
        
        if comparison < 0:
            msg = f"""警告：选择的版本低于当前版本！

当前版本: v{self.current_version}
选择版本: v{new_version}

确定要降级到旧版本吗？"""
            return messagebox.askyesno("版本警告", msg)
            
        elif comparison == 0:
            msg = f"""选择的版本与当前版本相同。

版本号: v{self.current_version}

确定要重新安装当前版本吗？"""
            return messagebox.askyesno("确认", msg)
            
        else:
            msg = f"""确认更新到新版本？

当前版本: v{self.current_version}
新版本: v{new_version}

更新过程中应用将暂时无法使用，
您的数据文件将被保留。

是否继续？"""
            return messagebox.askyesno("确认更新", msg)
    
    def _apply_update(self, source_path, temp_dir, on_complete=None):
        """应用更新"""
        try:
            self.log("\n" + "=" * 60)
            self.log("开始本地更新...", "COMMAND")
            self.log("=" * 60)
            
            if self.progress_callback:
                self.progress_callback(20, "备份用户数据...")
            
            # 备份
            backup_dir = self._backup_user_data()
            self.log(f"用户数据已备份到: {backup_dir}")
            
            if self.progress_callback:
                self.progress_callback(60, "正在替换文件...")
            
            # 复制文件
            self._copy_files(source_path)
            
            if self.progress_callback:
                self.progress_callback(100, "更新完成！")
            
            self.log("更新安装成功！", "SUCCESS")
            
            if on_complete:
                on_complete(True)
                
        except Exception as e:
            self.log(f"更新失败: {e}", "ERROR")
            if on_complete:
                on_complete(False)
        finally:
            self.is_updating = False
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except:
                pass
            if self.status_callback:
                self.status_callback("ready")
    
    def _backup_user_data(self):
        """备份用户数据"""
        backup_dir = self.project_dir / f"backup_{self._timestamp()}"
        backup_dir.mkdir(exist_ok=True)
        
        # 备份uploads和outputs
        for folder in ["uploads", "outputs"]:
            src = self.project_dir / folder
            if src.exists():
                dst = backup_dir / folder
                shutil.copytree(src, dst, ignore_errors=True)
        
        return backup_dir
    
    def _copy_files(self, source_path):
        """复制更新文件"""
        self.log("正在复制更新文件...")
        
        for file_name in UPDATE_FILES:
            src = source_path / file_name
            if src.exists():
                dst = self.project_dir / file_name
                shutil.copy2(src, dst)
                self.log(f"  已更新: {file_name}")
        
        # 更新templates目录
        src_templates = source_path / "templates"
        if src_templates.exists():
            dst_templates = self.project_dir / "templates"
            if dst_templates.exists():
                shutil.rmtree(dst_templates, ignore_errors=True)
            shutil.copytree(src_templates, dst_templates)
            self.log("  已更新: templates/")
    
    @staticmethod
    def _timestamp():
        return datetime.now().strftime('%Y%m%d_%H%M%S')
