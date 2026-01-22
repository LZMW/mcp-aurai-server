"""项目备份脚本 - 使用 Python 实现"""
import os
import shutil
import zipfile
from datetime import datetime

# 配置
PROJECT_DIR = r"[项目目录]"
BACKUP_DIR = r"D:\backups"
EXCLUDE_DIRS = {"venv", "__pycache__", ".pytest_cache", ".git", "build", "dist", ".backup_temp"}
EXCLUDE_FILES = {".pyc", ".pyo", ".pyd", ".py.class"}

def should_exclude(path):
    """判断是否应该排除某个文件/目录"""
    path_parts = path.split(os.sep)

    # 检查目录
    for part in path_parts:
        if part in EXCLUDE_DIRS:
            return True

    # 检查文件扩展名
    for ext in EXCLUDE_FILES:
        if path.endswith(ext):
            return True

    return False

def create_backup():
    """创建项目备份"""
    # 创建备份目录
    os.makedirs(BACKUP_DIR, exist_ok=True)

    # 生成时间戳
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_name = f"mcp-aurai-advisor-{timestamp}.zip"
    backup_path = os.path.join(BACKUP_DIR, backup_name)

    print("=" * 50)
    print("  MCP Aurai Advisor Project Backup")
    print("=" * 50)
    print()
    print(f"Creating backup: {backup_name}")
    print(f"Project: {PROJECT_DIR}")
    print(f"Destination: {BACKUP_DIR}")
    print()

    # 创建 ZIP 文件
    with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        count = 0
        for root, dirs, files in os.walk(PROJECT_DIR):
            # 过滤掉不需要的目录
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]

            for file in files:
                file_path = os.path.join(root, file)

                # 跳过特殊文件和设备文件
                if 'nul' in file_path.lower() or not os.path.isfile(file_path):
                    continue

                # 检查是否应该排除
                if should_exclude(file_path):
                    continue

                try:
                    # 计算相对路径
                    rel_path = os.path.relpath(file_path, PROJECT_DIR)

                    # 添加到 ZIP
                    zipf.write(file_path, rel_path)
                    count += 1

                    # 显示进度（每10个文件）
                    if count % 10 == 0:
                        print(f"  Files processed: {count}", end='\r')
                except (ValueError, OSError) as e:
                    # 跳过无法处理的文件
                    continue

    print()
    print()
    print("=" * 50)
    print("  Backup Completed!")
    print("=" * 50)
    print()
    print(f"Total files: {count}")
    print(f"Backup saved: {backup_path}")
    print(f"Size: {os.path.getsize(backup_path) / 1024 / 1024:.2f} MB")
    print()

    return backup_path

if __name__ == "__main__":
    try:
        backup_path = create_backup()
        print("Success! Backup completed.")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
