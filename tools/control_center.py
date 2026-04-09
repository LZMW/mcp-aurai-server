"""
Aurai 配置生成工具 - 简化版

功能：
1. Audit: 查看历史对话记录
2. Config: 生成配置文件（包含完整的安装指导）
"""

import json
import os
import re
import sys
import threading
import time
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
from tkinter import (
    ttk,
    Button,
    Entry,
    Frame,
    Label,
    Listbox,
    scrolledtext,
    StringVar,
    Text,
    Tk,
    END,
    VERTICAL,
    HORIZONTAL,
    filedialog,
    messagebox,
)
from typing import Optional

# 获取项目根目录（支持打包后的 EXE）
if getattr(sys, 'frozen', False):
    # 打包后的 EXE 环境
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller 打包后的临时目录
        BUNDLE_DIR = Path(sys._MEIPASS)
        PROJECT_ROOT = Path(sys.executable).parent
    else:
        PROJECT_ROOT = Path(sys.executable).parent
else:
    # 开发环境
    PROJECT_ROOT = Path(__file__).parent.parent

# 添加 src 到 Python 路径
src_path = PROJECT_ROOT / "src"
if src_path.exists():
    sys.path.insert(0, str(src_path))


class AuraiConfigTool:
    """Aurai 配置工具 - 简化版主界面"""

    def __init__(self, root: Tk):
        self.root = root
        self.root.title("Aurai 配置工具 v2.3")
        self.root.geometry("1000x700")

        # 配置文件路径
        self.env_path = PROJECT_ROOT / ".env"
        self.history_path = Path.home() / ".mcp-aurai" / "history.json"

        # 创建界面
        self.create_widgets()

        # 加载初始数据
        self.load_config()
        self.load_history()

    def create_widgets(self):
        """创建界面组件"""
        # 创建 Notebook（Tab 页）
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)

        # 创建两个 Tab
        self.tab_config = Frame(self.notebook)
        self.tab_audit = Frame(self.notebook)

        self.notebook.add(self.tab_config, text="  ⚙️ 生成配置  ")
        self.notebook.add(self.tab_audit, text="  📜 对话历史  ")

        # 创建各个 Tab 的内容
        self.create_config_tab()
        self.create_audit_tab()

    def create_config_tab(self):
        """创建配置生成 Tab"""
        # 主容器 - 使用 PanedWindow 分割左右
        paned = ttk.PanedWindow(self.tab_config, orient=HORIZONTAL)
        paned.pack(fill="both", expand=True, padx=10, pady=10)

        # 左侧：配置区域
        left_frame = Frame(paned)
        paned.add(left_frame, weight=3)

        # 右侧：帮助面板
        help_panel = Frame(paned, width=250, bg="#f5f5f5", relief="raised", bd=1)
        paned.add(help_panel, weight=1)

        # 配置预设选择
        preset_frame = Frame(left_frame, bg="#e3f2fd", relief="raised", bd=1)
        preset_frame.pack(fill="x", pady=(0, 15), padx=5)

        Label(preset_frame, text="🚀 快速配置预设", font=("Microsoft YaHei", 11, "bold"), bg="#e3f2fd").pack(pady=10)

        self.config_preset = StringVar(value="custom")
        preset_options = [
            "custom - 自定义中转站（推荐使用 GLM-4.7）",
        ]

        preset_dropdown = ttk.Combobox(preset_frame, textvariable=self.config_preset, values=preset_options, state="readonly", font=("Microsoft YaHei", 10))
        preset_dropdown.pack(fill="x", padx=15, pady=(0, 10))
        preset_dropdown.bind("<<ComboboxSelected>>", self.on_preset_changed)

        # 配置字段容器 - 使用 grid 布局
        config_container = Frame(left_frame)
        config_container.pack(fill="both", expand=True, padx=5)

        self.config_vars = {}
        self.config_combos = {}

        # 字段定义（只保留必要的配置项）
        field_definitions = [
            ("AURAI_API_KEY", "API 密钥", "entry", None),
            ("AURAI_BASE_URL", "API 地址 (Base URL)", "entry", None),
            ("AURAI_MODEL", "模型名称（推荐 GLM-4.7）", "combo_entry", []),
            ("AURAI_CONTEXT_WINDOW", "上下文窗口（默认 200000，基于 GLM-4.7）", "entry", None),
            ("AURAI_MAX_MESSAGE_TOKENS", "单条消息最大 Tokens（默认 150000）", "entry", None),
            ("AURAI_MAX_TOKENS", "最大输出 Tokens（默认 32000）", "entry", None),
            ("AURAI_MAX_ITERATIONS", "最大迭代次数 (5-20)", "entry", None),
            ("AURAI_MAX_HISTORY", "对话历史最大保存数 (10-100)", "entry", None),
            ("AURAI_TEMPERATURE", "温度参数 (0.0-2.0)", "entry", None),
            ("AURAI_HISTORY_LOCK_TIMEOUT", "历史文件锁超时（秒，默认 10）", "entry", None),
            ("AURAI_ENABLE_HISTORY_SUMMARY", "启用历史摘要（true/false）", "entry", None),
            ("AURAI_HISTORY_SUMMARY_KEEP_RECENT", "摘要后保留最近原始轮次（默认 3）", "entry", None),
            ("AURAI_HISTORY_SUMMARY_TRIGGER", "触发历史摘要阈值（默认 8）", "entry", None),
        ]

        row = 0
        for key, label_text, field_type, options in field_definitions:
            Label(config_container, text=label_text, font=("Microsoft YaHei", 10)).grid(row=row, column=0, sticky="w", pady=5, padx=5)

            if field_type == "entry":
                var = StringVar()
                entry = Entry(config_container, textvariable=var, font=("Consolas", 10), width=40)
                entry.grid(row=row, column=1, sticky="ew", pady=5, padx=5)
                self.config_vars[key] = var

            elif field_type == "combo":
                var = StringVar()
                combo = ttk.Combobox(config_container, textvariable=var, values=options, state="readonly", font=("Microsoft YaHei", 10), width=38)
                combo.grid(row=row, column=1, sticky="ew", pady=5, padx=5)
                self.config_vars[key] = var
                self.config_combos[key] = combo

            elif field_type == "combo_entry":
                var = StringVar()
                # 创建一个复合控件：下拉框 + 手动输入 + 刷新按钮
                frame = Frame(config_container)
                frame.grid(row=row, column=1, sticky="ew", pady=5, padx=5)

                combo = ttk.Combobox(frame, textvariable=var, state="readonly", font=("Microsoft YaHei", 10), width=25)
                combo.pack(side="left")
                self.config_combos[key] = combo

                # 添加模型预设（当提供商改变时更新）
                self.model_combo = combo

                entry = Entry(frame, textvariable=var, font=("Consolas", 10), width=12)
                entry.pack(side="left", padx=(5, 0))
                self.config_vars[key] = var

                # 添加刷新按钮
                refresh_btn = Button(
                    frame,
                    text="🔄",
                    command=self.refresh_model_list,
                    font=("Microsoft YaHei", 9),
                    width=3,
                    bg="#E3F2FD",
                    relief="raised",
                )
                refresh_btn.pack(side="left", padx=(5, 0))

            row += 1

        # 配置容器列权重
        config_container.grid_columnconfigure(1, weight=1)

        # 按钮区
        button_frame = Frame(left_frame)
        button_frame.pack(fill="x", pady=15, padx=5)

        Button(
            button_frame,
            text="💾 生成配置文件",
            command=self.save_config,
            bg="#2196F3",
            fg="white",
            font=("Microsoft YaHei", 11, "bold"),
            width=15,
        ).pack(side="left", padx=5)

        Button(
            button_frame,
            text="🔄 重新加载",
            command=self.load_config,
            font=("Microsoft YaHei", 11),
            width=12,
        ).pack(side="left", padx=5)

        # 状态消息
        self.status_message = Label(left_frame, text="", fg="green", font=("Microsoft YaHei", 10))
        self.status_message.pack(pady=5)

        # 添加帮助信息
        self.create_help_panel(help_panel)

    def create_audit_tab(self):
        """创建对话审计 Tab"""
        # 分割为左右两部分
        paned = ttk.PanedWindow(self.tab_audit, orient=HORIZONTAL)
        paned.pack(fill="both", expand=True, padx=10, pady=10)

        # 左侧：对话列表
        left_frame = Frame(paned)
        paned.add(left_frame, weight=1)

        Label(left_frame, text="对话历史记录", font=("Microsoft YaHei", 11, "bold")).pack(pady=5)

        self.history_listbox = Listbox(left_frame, font=("Consolas", 10))
        self.history_listbox.pack(fill="both", expand=True, padx=5, pady=5)
        self.history_listbox.bind("<<ListboxSelect>>", self.on_history_select)

        Button(left_frame, text="🔄 刷新", command=self.load_history).pack(fill="x", padx=5, pady=5)

        # 右侧：对话详情
        right_frame = Frame(paned)
        paned.add(right_frame, weight=2)

        Label(right_frame, text="对话详情", font=("Microsoft YaHei", 11, "bold")).pack(pady=5)

        self.detail_text = scrolledtext.ScrolledText(
            right_frame, wrap="word", font=("Consolas", 9)
        )
        self.detail_text.pack(fill="both", expand=True, padx=5, pady=5)

    def load_history(self):
        """加载历史对话"""
        self.history_listbox.delete(0, END)

        try:
            if not self.history_path.exists():
                self.history_listbox.insert(END, "未找到历史文件")
                return

            with open(self.history_path, "r", encoding="utf-8") as f:
                history = json.load(f)

            if not history:
                self.history_listbox.insert(END, "暂无对话记录")
                return

            for idx, entry in enumerate(history):
                entry_type = entry.get("type", "unknown")
                timestamp = entry.get("timestamp", "N/A")

                if entry_type == "consult":
                    problem_type = entry.get("problem_type", "unknown")
                    error_msg = entry.get("error_message", "")[:50]
                    display_text = f"#{idx + 1} [{timestamp}] 咨询: {problem_type} - {error_msg}..."
                elif entry_type == "sync_context":
                    operation = entry.get("operation", "unknown")
                    display_text = f"#{idx + 1} [{timestamp}] 同步: {operation}"
                elif entry_type == "progress":
                    result = entry.get("result", "unknown")
                    display_text = f"#{idx + 1} [{timestamp}] 进度: {result}"
                else:
                    display_text = f"#{idx + 1} [{timestamp}] {entry_type}"

                self.history_listbox.insert(END, display_text)

        except Exception as e:
            self.history_listbox.insert(END, f"加载历史失败: {e}")

    def on_history_select(self, event):
        """历史记录选择事件"""
        selection = self.history_listbox.curselection()
        if not selection:
            return

        idx = selection[0]
        try:
            with open(self.history_path, "r", encoding="utf-8") as f:
                history = json.load(f)

            if idx < len(history):
                entry = history[idx]
                formatted = json.dumps(entry, ensure_ascii=False, indent=2)
                self.detail_text.delete(1.0, END)
                self.detail_text.insert(1.0, formatted)

        except Exception as e:
            self.detail_text.delete(1.0, END)
            self.detail_text.insert(1.0, f"加载详情失败: {e}")

    def load_config(self):
        """加载配置"""
        try:
            if not self.env_path.exists():
                # 创建默认配置
                self.show_status("正在创建默认配置文件...", "orange")
                return

            with open(self.env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        key = key.strip()
                        value = value.strip()

                        if key in self.config_vars:
                            self.config_vars[key].set(value)

            self.show_status("配置加载成功！", "green")

        except Exception as e:
            self.show_status(f"加载配置失败: {e}", "red")

    def save_config(self):
        """保存配置 - 生成包含安装指导的 .env 文件"""
        try:
            # 弹出保存对话框
            default_filename = f"aurai-config-{datetime.now().strftime('%Y%m%d-%H%M%S')}.env"
            file_path = filedialog.asksaveasfilename(
                title="保存配置文件",
                defaultextension=".env",
                initialfile=default_filename,
                filetypes=[
                    ("环境配置文件", "*.env"),
                    ("所有文件", "*.*")
                ],
                initialdir=str(PROJECT_ROOT)
            )

            # 用户取消保存
            if not file_path:
                self.show_status("已取消保存", "blue")
                return

            # 收集配置值
            config_values = {}
            for key, var in self.config_vars.items():
                value = var.get().strip()
                if value:
                    config_values[key] = value

            # 获取关键配置用于生成说明
            base_url = config_values.get("AURAI_BASE_URL", "")
            model = config_values.get("AURAI_MODEL", "")

            # 写入文件（包含详细说明）
            with open(file_path, "w", encoding="utf-8") as f:
                # ========== AI 专用引导 ==========
                f.write("################################################################################\n")
                f.write("# 🤖 AI 助手专用安装引导\n")
                f.write("################################################################################\n")
                f.write("#\n")
                f.write("# 【重要】当 AI 助手读取此配置文件时，请按照以下步骤执行：\n")
                f.write("#\n")
                f.write("# ✅ 第一步：环境检查\n")
                f.write("#   1. 确认 Python 版本：python --version (需要 3.10+)\n")
                f.write("#   2. 确认 pip 可用：pip --version\n")
                f.write("#   3. 确认项目目录存在（即此文件所在目录）\n")
                f.write("#\n")
                f.write("# ✅ 第二步：安装依赖\n")
                f.write("#   cd [项目根目录]\n")
                f.write("#   pip install -e .\n")
                f.write("#   # 或使用开发模式安装所有依赖：\n")
                f.write("#   pip install -e \".[all-dev]\"\n")
                f.write("#\n")
                f.write("# ✅ 第三步：配置 Claude Code（推荐）\n")
                f.write("#   1. 使用下方 \"Claude Code 配置指南\" 中的命令\n")
                f.write("#   2. 命令格式：claude mcp add --scope user --transport stdio aurai-advisor --env KEY=VALUE ... -- python -m mcp_aurai.server\n")
                f.write("#   3. ⚠️ 重要：使用 --scope user 确保在所有项目中都可用，避免每次切换目录都要重新安装\n")
                f.write("#   4. 执行命令后重启 Claude Code\n")
                f.write("#   5. 验证：在对话中描述编程问题，AI 会判断是否调用 consult_aurai 工具\n")
                f.write("#\n")
                f.write("# ✅ 第四步：验证安装\n")
                f.write("#   python -m mcp_aurai.server\n")
                f.write("#   # 应该看到：\"MCP server running on stdio\"\n")
                f.write("#\n")
                f.write("# 【故障排查】如果遇到问题，请查看文件底部的故障排查章节\n")
                f.write("#\n")
                f.write("################################################################################\n")
                f.write("#\n")
                f.write("# 【项目信息】\n")
                f.write(f"# 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"# 配置工具: Aurai 配置工具 v2.0\n")
                f.write(f"# 推荐模型: GLM-4.7\n")
                f.write(f"# 当前模型: {model}\n")
                if base_url:
                    f.write(f"# API 地址: {base_url}\n")
                f.write("#\n")
                f.write("################################################################################\n")
                f.write("#\n")

                # ========== Claude Code 配置命令 ==========
                f.write("################################################################################\n")
                f.write("# 🚀 Claude Code 配置命令\n")
                f.write("################################################################################\n")
                f.write("#\n")
                f.write("# ⚠️ 重要：使用 --scope user 确保在所有项目中都可用\n")
                f.write("#\n")
                f.write("# 【执行下方命令添加 MCP 服务器】\n")
                f.write(f"# claude mcp add --scope user --transport stdio aurai-advisor \\\n")
                for key, value in config_values.items():
                    f.write(f"#   --env {key}=\"{value}\" \\\n")

                # 动态检测 Python 路径
                python_path = sys.executable
                # 如果是开发环境的虚拟环境，使用相对路径
                if not getattr(sys, 'frozen', False):
                    # 开发环境 - 使用项目根目录的相对路径
                    project_venv = PROJECT_ROOT / "venv" / "Scripts" / "python.exe"
                    if project_venv.exists():
                        python_path = str(project_venv).replace(str(PROJECT_ROOT), "[项目根目录]")
                    else:
                        python_path = "[你的Python路径]"

                f.write(f"#   -- \"{python_path}\" \"-m\" \"mcp_aurai.server\"\n")
                f.write("#\n")
                f.write("# 【常用命令】\n")
                f.write("# 查看配置: claude mcp get aurai-advisor\n")
                f.write("# 列出所有: claude mcp list\n")
                f.write("# 删除配置: claude mcp remove aurai-advisor -s user\n")
                f.write("#\n")
                f.write("################################################################################\n")
                f.write("#\n")

                # ========== 配置说明 ==========
                f.write("################################################################################\n")
                f.write("# Aurai MCP Server - 配置文件\n")
                f.write("################################################################################\n")
                f.write("#\n")
                f.write("# 【配置方式】\n")
                f.write("# 此配置文件通过环境变量的方式由 Claude Code 读取\n")
                f.write("# 使用上方生成的 'claude mcp add' 命令进行配置\n")
                f.write("#\n")
                f.write("################################################################################\n")
                f.write("# 配置项说明\n")
                f.write("################################################################################\n")
                f.write("#\n")
                f.write("# AURAI_API_KEY             - API 密钥（必填）\n")
                f.write("# AURAI_BASE_URL           - API 基础地址（必填）\n")
                f.write("#                            OpenAI 兼容 API 的完整地址\n")
                f.write("# AURAI_MODEL               - 模型名称\n")
                f.write("#                            推荐使用 GLM-4.7 系列\n")
                f.write("# AURAI_CONTEXT_WINDOW      - 上下文窗口大小（默认：200000，基于 GLM-4.7）\n")
                f.write("#                            使用其他模型时可根据实际情况调整\n")
                f.write("# AURAI_MAX_MESSAGE_TOKENS  - 单条消息最大 Tokens（默认：150000）\n")
                f.write("#                            用于大文件分批发送\n")
                f.write("# AURAI_MAX_TOKENS           - 最大输出 Tokens（默认：32000）\n")
                f.write("# AURAI_MAX_ITERATIONS      - 最大对话轮数（默认 10）\n")
                f.write("# AURAI_MAX_HISTORY          - 对话历史最大保存数（默认 50）\n")
                f.write("# AURAI_TEMPERATURE         - 温度参数 0.0-2.0（默认 0.7）\n")
                f.write("# AURAI_HISTORY_LOCK_TIMEOUT - 历史文件锁等待时间（秒，默认 10）\n")
                f.write("# AURAI_ENABLE_HISTORY_SUMMARY - 是否启用历史摘要（默认 true）\n")
                f.write("# AURAI_HISTORY_SUMMARY_KEEP_RECENT - 摘要后保留最近原始轮次（默认 3）\n")
                f.write("# AURAI_HISTORY_SUMMARY_TRIGGER - 触发历史摘要阈值（默认 8）\n")
                f.write("#\n")
                f.write("# 【以下配置自动管理，无需手动设置】\n")
                f.write("# AURAI_ENABLE_PERSISTENCE   - 对话历史持久化（自动启用）\n")
                f.write("# AURAI_HISTORY_PATH        - 历史文件路径（自动保存到用户目录）\n")
                f.write("# AURAI_LOG_LEVEL           - 日志级别（默认 INFO）\n")
                f.write("#\n")
                f.write("################################################################################\n")
                f.write("# 配置内容\n")
                f.write("################################################################################\n")
                f.write("#\n")

                # 写入配置项
                for key, value in config_values.items():
                    f.write(f"{key}={value}\n")

                f.write("\n")
                f.write("################################################################################\n")
                f.write("# 📚 安装和使用指南\n")
                f.write("################################################################################\n")
                f.write("#\n")
                f.write("# 【快速安装】\n")
                f.write("# 1. 安装依赖:\n")
                f.write("#    pip install -e .\n")
                f.write("#    # 或安装所有开发依赖:\n")
                f.write("#    pip install -e \".[all-dev]\"\n")
                f.write("#\n")
                f.write("# 2. 配置 MCP（使用上方生成的命令）:\n")
                f.write("#    claude mcp add --scope user --transport stdio aurai-advisor --env AURAI_API_KEY=\"...\" ...\n")
                f.write("#\n")
                f.write("# 3. 验证安装:\n")
                f.write("#    claude mcp list\n")
                f.write("#\n")
                f.write("# 4. 测试 MCP 工具:\n")
                f.write("#    在 Claude Code 对话中直接描述编程问题即可\n")
                f.write("#    例如：\"我遇到了一个 KeyError 问题...\"\n")
                f.write("#    AI 会自动判断是否调用 consult_aurai 工具\n")
                f.write("#    sync_context 现在支持直接上传代码/配置等文本文件，无需手动改名成 .txt\n")
                f.write("#\n")
                f.write("################################################################################\n")
                f.write("# 🔧 故障排查指南\n")
                f.write("################################################################################\n")
                f.write("#\n")
                f.write("# 【问题 1】MCP 工具没有出现\n")
                f.write("# 原因: MCP 未正确配置或 Claude Code 未重启\n")
                f.write("# 解决:\n")
                f.write("#   claude mcp list  # 检查配置\n")
                f.write("#   claude mcp get aurai-advisor  # 查看详细配置\n")
                f.write("#   # 若配置错误，删除后重新添加:\n")
                f.write("#   claude mcp remove aurai-advisor -s user\n")
                f.write("#   claude mcp add --scope user ...\n")
                f.write("#\n")
                f.write("# 【问题 1.1】每次打开 Claude Code 都要重新安装？\n")
                f.write("# 原因: 使用了默认的本地范围（local），只在特定目录可用\n")
                f.write("# 解决: 使用 --scope user 重新安装\n")
                f.write("#\n")
                f.write("# 【问题 2】ModuleNotFoundError: No module named 'mcp_aurai'\n")
                f.write("# 原因: 未安装依赖或未在正确的 Python 环境\n")
                f.write("# 解决:\n")
                f.write("#   pip install -e .\n")
                f.write("#   # 如果使用虚拟环境，确保已激活:\n")
                f.write("#   venv\\Scripts\\activate  # Windows\n")
                f.write("#   source venv/bin/activate  # macOS/Linux\n")
                f.write("#\n")
                f.write("# 【问题 3】401 Unauthorized\n")
                f.write("# 原因: API 密钥错误或无效\n")
                f.write("# 解决:\n")
                f.write("#   - 检查 AURAI_API_KEY 是否正确\n")
                f.write("#   - 访问提供商平台重新生成密钥\n")
                f.write("#   - 确认密钥没有过期\n")
                f.write("#\n")
                f.write("# 【问题 4】404 Model not found\n")
                f.write("# 原因: 模型名称错误\n")
                f.write("# 解决:\n")
                f.write("#   - 使用配置工具的\"刷新模型\"功能获取正确列表\n")
                f.write("#   - 检查模型名称拼写\n")
                f.write("#   - 确认该模型在当前提供商可用\n")
                f.write("#\n")
                f.write("# 【问题 5】Connection timeout\n")
                f.write("# 原因: 网络问题或 API 地址错误\n")
                f.write("# 解决:\n")
                f.write("#   - 检查网络连接\n")
                f.write("#   - 确认 AURAI_BASE_URL 正确（custom 提供商必填）\n")
                f.write("#   - 尝试使用官方 API（不使用第三方中转站）\n")
                f.write("#\n")
                f.write("# 【问题 6】Permission denied when writing to history file\n")
                f.write("# 原因: 历史文件路径无写入权限\n")
                f.write("# 解决:\n")
                f.write("#   - 检查 AURAI_HISTORY_PATH 路径是否正确\n")
                f.write("#   - 确保目录存在且可写\n")
                f.write("#   - 或禁用持久化: AURAI_ENABLE_PERSISTENCE=false\n")
                f.write("#\n")
                f.write("################################################################################\n")
                f.write("# 📖 支持的服务商和获取 API 密钥\n")
                f.write("################################################################################\n")
                f.write("#\n")
                f.write("# 【智谱 AI】（推荐使用 GLM-4.7）\n")
                f.write("# 官网: https://open.bigmodel.cn/\n")
                f.write("# 获取密钥: https://open.bigmodel.cn/usercenter/apikeys\n")
                f.write("# 推荐模型: glm-4.7, glm-4.7-flashx\n")
                f.write("# API 地址: https://open.bigmodel.cn/api/paas/v4/\n")
                f.write("#\n")
                f.write("# 【其他 OpenAI 兼容 API】\n")
                f.write("# 本项目使用 OpenAI 兼容 API，可接入任何兼容服务：\n")
                f.write("# • DeepSeek: https://api.deepseek.com/v1\n")
                f.write("# • 第三方中转站：根据提供商提供的地址\n")
                f.write("# • 其他兼容 GPT/DeepSeek/Qwen 等模型的服务\n")
                f.write("#\n")
                f.write("################################################################################\n")
                f.write("# 📞 技术支持\n")
                f.write("################################################################################\n")
                f.write("#\n")
                f.write("# - 查看完整文档: docs/用户手册.md\n")
                f.write("# - 提交问题: GitHub Issues\n")
                f.write("# - 查看日志: 设置 AURAI_LOG_LEVEL=DEBUG\n")
                f.write("# - 注意：本配置工具目前主要负责生成配置；历史审计界面仍以默认会话历史为主\n")
                f.write("#\n")
                f.write("################################################################################\n")
                f.write("# 配置文件结束\n")
                f.write("################################################################################\n")
                f.write("#\n")
                f.write("# 【提示】保存此文件后，请按照上方的 \"AI 助手专用安装引导\" 执行安装\n")
                f.write("#\n")

            # 同时更新默认 .env 文件（用于本地运行）
            with open(self.env_path, "w", encoding="utf-8") as f:
                for key, value in config_values.items():
                    f.write(f"{key}={value}\n")

            # 显示保存位置
            file_path_obj = Path(file_path)
            self.show_status(f"配置已保存到: {file_path_obj.name}", "green")

            # 询问是否打开目录
            self.root.after(2000, lambda: self._ask_open_folder(file_path_obj.parent))

        except Exception as e:
            self.show_status(f"保存配置失败: {e}", "red")

    def _ask_open_folder(self, folder_path: Path):
        """询问是否打开保存目录"""
        result = messagebox.askyesno(
            "配置已保存",
            f"配置文件已成功保存！\n\n文件包含完整的安装指导。\n\n是否打开文件所在目录？",
            icon="question"
        )

        if result:
            try:
                if os.name == 'nt':
                    os.startfile(folder_path)
                elif sys.platform == 'darwin':
                    subprocess.run(['open', folder_path])
                else:
                    subprocess.run(['xdg-open', folder_path])
            except Exception as e:
                self.show_status(f"打开目录失败: {e}", "red")

    def show_status(self, message: str, color: str):
        """显示状态消息"""
        self.status_message.config(text=message, fg=color)
        # 3秒后清除
        self.root.after(3000, lambda: self.status_message.config(text=""))

    # ========== API 模型列表获取 ==========
    def fetch_models_from_api(self, provider: str, base_url: str, api_key: str) -> list[str]:
        """
        从 API 获取模型列表
        支持 OpenAI 兼容的 /v1/models 端点
        """
        try:
            # 构建自定义提供商使用配置的 base_url
            if not base_url:
                return []
            api_url = f"{base_url.rstrip('/')}/models"

            # 如果没有 API Key，无法调用
            if not api_key:
                return []

            # 创建请求
            request = urllib.request.Request(api_url)
            request.add_header("Authorization", f"Bearer {api_key}")
            request.add_header("Content-Type", "application/json")

            # 发送请求（5秒超时）
            with urllib.request.urlopen(request, timeout=5) as response:
                data = json.loads(response.read().decode())

                # 解析模型列表（OpenAI 格式）
                if "data" in data:
                    models = [item["id"] for item in data["data"]]
                    return sorted(models, reverse=True)  # 最新的在前
                else:
                    return []

        except urllib.error.HTTPError:
            # API 调用失败（401/403 等），返回预设列表
            return self.MODEL_PRESETS.get("custom", [])
        except urllib.error.URLError:
            # 网络错误，返回预设列表
            return self.MODEL_PRESETS.get("custom", [])
        except Exception:
            # 其他错误，返回预设列表
            return self.MODEL_PRESETS.get("custom", [])

    def refresh_model_list(self):
        """刷新模型列表（从 API 获取）"""
        base_url = self.config_vars.get("AURAI_BASE_URL", StringVar()).get()
        api_key = self.config_vars.get("AURAI_API_KEY", StringVar()).get()

        if not api_key:
            self.show_status("请先配置 API 密钥", "orange")
            return

        if not base_url:
            self.show_status("请先配置 API 地址", "orange")
            return

        # 显示加载状态
        self.show_status("正在获取模型列表...", "blue")
        self.root.update_idletasks()

        # 在后台线程中获取模型列表
        def fetch_in_background():
            models = self.fetch_models_from_api("custom", base_url, api_key)

            # 更新 UI（必须在主线程中）
            self.root.after(0, lambda: self._update_model_combo(models))

        thread = threading.Thread(target=fetch_in_background, daemon=True)
        thread.start()

    def _update_model_combo(self, models: list[str]):
        """更新模型下拉列表（在主线程中调用）"""
        if models:
            self.model_combo['values'] = models
            current = self.config_vars["AURAI_MODEL"].get()
            if current not in models and models:
                self.config_vars["AURAI_MODEL"].set(models[0])
            self.show_status(f"已加载 {len(models)} 个模型", "green")
        else:
            # 如果 API 调用失败，使用预设列表
            fallback_models = self.MODEL_PRESETS.get("custom", [])
            self.model_combo['values'] = fallback_models
            if fallback_models:
                self.show_status(f"API 调用失败，使用预设列表（{len(fallback_models)} 个模型）", "orange")
            else:
                self.show_status("无法获取模型列表，请手动输入", "red")

    # ========== 模型预设配置 ==========
    # 推荐模型列表（基于 GLM-4.7 优化）
    MODEL_PRESETS = {
        "custom": [
            # 智谱 AI GLM-4.7 系列（推荐）
            "glm-4.7",
            "glm-4.7-flashx",
            # 智谱 AI 其他模型
            "glm-4-flash",
            "glm-4-plus",
            "glm-4-air",
            "glm-3-turbo",
            # DeepSeek
            "deepseek-v3-1-250821",
            "deepseek-chat",
            "deepseek-coder",
            # 其他常用模型
            "gpt-4o",
            "gpt-4o-mini",
            "Qwen/Qwen2.5-72B-Instruct",
            "meta-llama/Llama-3.1-70B-Instruct",
        ],
    }

    # 配置预设值
    CONFIG_PRESETS = {
        "custom": {
            "AURAI_BASE_URL": "https://open.bigmodel.cn/api/paas/v4/",
            "AURAI_MODEL": "glm-4.7",
            "AURAI_CONTEXT_WINDOW": "200000",
            "AURAI_MAX_MESSAGE_TOKENS": "150000",
            "AURAI_MAX_TOKENS": "32000",
            "AURAI_MAX_ITERATIONS": "10",
            "AURAI_MAX_HISTORY": "50",
            "AURAI_TEMPERATURE": "0.7",
            "AURAI_HISTORY_LOCK_TIMEOUT": "10",
            "AURAI_ENABLE_HISTORY_SUMMARY": "true",
            "AURAI_HISTORY_SUMMARY_KEEP_RECENT": "3",
            "AURAI_HISTORY_SUMMARY_TRIGGER": "8",
        },
    }

    def on_preset_changed(self, event):
        """配置预设改变事件"""
        preset = self.config_preset.get()
        # 提取预设键名（例如 "custom - 自定义中转站" -> "custom"）
        preset_key = preset.split(" - ")[0] if " - " in preset else preset

        if preset_key in self.CONFIG_PRESETS:
            config = self.CONFIG_PRESETS[preset_key]
            for key, value in config.items():
                if key in self.config_vars:
                    self.config_vars[key].set(value)

            # 使用预设列表
            if preset_key in self.MODEL_PRESETS:
                self.model_combo['values'] = self.MODEL_PRESETS[preset_key]
                if self.MODEL_PRESETS[preset_key]:
                    self.config_vars["AURAI_MODEL"].set(self.MODEL_PRESETS[preset_key][0])

            self.show_status(f"已应用预设: {preset}", "green")

            # 如果有 API Key，自动刷新模型列表
            api_key = self.config_vars.get("AURAI_API_KEY", StringVar()).get()
            if api_key:
                self.root.after(500, self.refresh_model_list)  # 延迟 500ms 执行

    def on_provider_changed(self, event):
        """提供商改变事件 - 已废弃（仅保留 custom）"""
        pass

    def create_help_panel(self, parent):
        """创建右侧帮助面板"""
        # 标题
        title = Label(parent, text="📖 配置指南", font=("Microsoft YaHei", 12, "bold"), bg="#f5f5f5")
        title.pack(pady=10)

        # 帮助内容（可滚动）
        help_frame = Frame(parent, bg="#f5f5f5")
        help_frame.pack(fill="both", expand=True, padx=10)

        help_text = scrolledtext.ScrolledText(
            help_frame,
            wrap="word",
            font=("Microsoft YaHei", 9),
            bg="#f5f5f5",
            fg="#333",
            height=25,
            relief="flat",
        )
        help_text.pack(fill="both", expand=True)

        # 帮助内容
        content = """📋 配置说明

【API 密钥】
必填项，从各平台获取。

【API 地址】
OpenAI 兼容 API 的完整地址。
智谱 AI: https://open.bigmodel.cn/api/paas/v4/
DeepSeek: https://api.deepseek.com/v1
其他中转站: 根据提供商填写

【模型名称】
推荐使用 GLM-4.7 系列：
• glm-4.7（旗舰版，200K 上下文）
• glm-4.7-flashx（轻量高速版）
可从下拉列表选择，或手动输入。
点击 🔄 按钮可从 API 获取最新模型列表。

【Token 配置（默认基于 GLM-4.7）】
• 上下文窗口：200000 tokens
• 单条消息最大：150000 tokens
• 最大输出：32000 tokens
使用其他模型时可调整这些值。

【历史能力】
• 支持历史文件锁与原子写入
• 支持较早历史自动摘要
• 可通过下方新增字段调整摘要保留轮次和触发阈值

【文件上传】
• sync_context 现在可以直接上传代码/配置等文本文件
• 不再要求手动把 .py / .js / .json 复制成 .txt
• 图片、压缩包、可执行文件等二进制内容会被跳过

【GLM-4.7 优势】
• 200K 上下文窗口
• 强大的编码和推理能力
• 支持深度思考模式
• 完美适合代码审查和复杂任务

💡 提示：
选择预设可自动填充 GLM-4.7 优化配置。

📝 生成后：
配置文件包含完整的安装指导，
可直接发给 AI 助手读取并执行安装。
"""
        help_text.insert(1.0, content)
        help_text.config(state="disabled")  # 只读


def main():
    """主函数"""
    root = Tk()
    app = AuraiConfigTool(root)
    root.mainloop()


if __name__ == "__main__":
    main()
