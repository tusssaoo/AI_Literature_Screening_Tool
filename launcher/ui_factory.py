#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UI组件工厂 - 创建各种UI元素
"""

import tkinter as tk
from tkinter import ttk
from .config import Colors


class UIFactory:
    """UI组件工厂类"""
    
    def __init__(self, root):
        self.root = root
        
    def setup_styles(self):
        """设置样式"""
        style = ttk.Style()
        style.theme_use('clam')
        
        # 配置进度条样式
        style.configure("Horizontal.TProgressbar", 
                       thickness=20, 
                       background=Colors.PRIMARY,
                       troughcolor=Colors.LIGHT)
    
    @staticmethod
    def create_button(parent, text, command, bg_color=Colors.PRIMARY, 
                      fg_color="white", width=15, font_size=11, **kwargs):
        """创建标准按钮"""
        btn = tk.Button(parent,
                       text=text,
                       font=("Microsoft YaHei", font_size),
                       bg=bg_color,
                       fg=fg_color,
                       activebackground=_darken_color(bg_color),
                       width=width,
                       height=1,
                       cursor="hand2",
                       command=command,
                       relief=tk.FLAT,
                       **kwargs)
        return btn
    



def _darken_color(hex_color, factor=0.8):
    """将颜色变暗"""
    # 简单的颜色处理，移除#后转换为RGB再变暗
    hex_color = hex_color.lstrip('#')
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    
    r = int(r * factor)
    g = int(g * factor)
    b = int(b * factor)
    
    return f"#{r:02x}{g:02x}{b:02x}"


def center_window(window, width=850, height=850):
    """窗口居中"""
    window.update_idletasks()
    x = (window.winfo_screenwidth() // 2) - (width // 2)
    y = (window.winfo_screenheight() // 2) - (height // 2)
    window.geometry(f'{width}x{height}+{x}+{y}')
