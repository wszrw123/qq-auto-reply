#!/usr/bin/env python3
"""
QQ 自动回复 Skill — macOS 版
通过 AppleScript + screencapture 实现 QQ 桌面端的自动化消息读取与回复。

功能：
  1. read   — 截取 QQ 当前聊天窗口截图，供 agent 分析消息内容
  2. reply  — 在当前聊天窗口输入文字并发送
  3. open   — 打开 QQ 并激活到前台
  4. search — 搜索联系人/群聊并打开对话
  5. list   — 截取 QQ 会话列表截图

使用方式：
  python3 qq_auto.py open                          # 激活 QQ 窗口
  python3 qq_auto.py read                          # 截取当前聊天窗口
  python3 qq_auto.py search --name "张三"          # 搜索并打开联系人
  python3 qq_auto.py reply --message "你好！"      # 发送消息
  python3 qq_auto.py reply --message "内容" --dry-run  # 只输入不发送

依赖：
  pip install pyautogui pillow
"""

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    import pyautogui
except ImportError:
    print("缺少依赖: pip install pyautogui pillow")
    sys.exit(1)

# ============================================================
# 配置
# ============================================================

SKILL_DIR = Path(__file__).parent
SCREENSHOT_DIR = SKILL_DIR / "screenshots"
SCREENSHOT_DIR.mkdir(exist_ok=True)

LOG_DIR = SKILL_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

QQ_APP_NAME = "QQ"
QQ_BUNDLE_ID = "com.tencent.qq"

# pyautogui 安全设置
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.3

# 日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_DIR / "qq_auto.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)


# ============================================================
# AppleScript 工具函数
# ============================================================

def run_applescript(script: str) -> str:
    """执行 AppleScript 并返回输出"""
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True, text=True, timeout=10
    )
    if result.returncode != 0:
        log.warning(f"AppleScript 错误: {result.stderr.strip()}")
    return result.stdout.strip()


def is_qq_running() -> bool:
    """检查 QQ 是否正在运行"""
    script = f'''
    tell application "System Events"
        return (name of processes) contains "{QQ_APP_NAME}"
    end tell
    '''
    return run_applescript(script) == "true"


def activate_qq():
    """激活 QQ 窗口到前台"""
    script = f'''
    tell application "{QQ_APP_NAME}"
        activate
    end tell
    '''
    run_applescript(script)
    time.sleep(0.5)


def launch_qq():
    """启动 QQ 应用"""
    script = f'''
    tell application "{QQ_APP_NAME}"
        launch
        activate
    end tell
    '''
    run_applescript(script)
    time.sleep(2)


def get_qq_window_info() -> dict:
    """获取 QQ 主窗口的位置和大小"""
    script = f'''
    tell application "System Events"
        tell process "{QQ_APP_NAME}"
            set frontWindow to front window
            set winPos to position of frontWindow
            set winSize to size of frontWindow
            return (item 1 of winPos) & "," & (item 2 of winPos) & "," & (item 1 of winSize) & "," & (item 2 of winSize)
        end tell
    end tell
    '''
    result = run_applescript(script)
    if result:
        parts = result.split(",")
        if len(parts) == 4:
            return {
                "x": int(parts[0]),
                "y": int(parts[1]),
                "width": int(parts[2]),
                "height": int(parts[3]),
            }
    return None


# ============================================================
# 截图功能
# ============================================================

def take_screenshot(region=None, filename=None) -> str:
    """截取屏幕截图
    
    Args:
        region: (x, y, width, height) 截图区域，None 为全屏
        filename: 文件名，None 自动生成
    
    Returns:
        截图文件路径
    """
    if filename is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"qq_{ts}.png"
    
    filepath = SCREENSHOT_DIR / filename
    
    if region:
        x, y, w, h = region
        # 使用 macOS screencapture 截取指定区域
        subprocess.run(
            ["screencapture", "-x", "-R", f"{x},{y},{w},{h}", str(filepath)],
            timeout=5
        )
    else:
        subprocess.run(
            ["screencapture", "-x", str(filepath)],
            timeout=5
        )
    
    if filepath.exists():
        log.info(f"截图已保存: {filepath}")
        return str(filepath)
    else:
        log.error("截图失败")
        return None


def screenshot_qq_window(filename=None) -> str:
    """截取 QQ 窗口截图"""
    activate_qq()
    time.sleep(0.3)
    
    win_info = get_qq_window_info()
    if win_info:
        region = (win_info["x"], win_info["y"], win_info["width"], win_info["height"])
        return take_screenshot(region=region, filename=filename)
    else:
        log.warning("无法获取 QQ 窗口信息，截取全屏")
        return take_screenshot(filename=filename)


# ============================================================
# 消息操作
# ============================================================

def type_text_via_applescript(text: str):
    """通过 AppleScript 输入文字（支持中文）"""
    # 先将文字写入剪贴板，再粘贴（最可靠的中文输入方式）
    script = f'''
    set the clipboard to "{text}"
    tell application "System Events"
        tell process "{QQ_APP_NAME}"
            keystroke "v" using command down
        end tell
    end tell
    '''
    run_applescript(script)
    time.sleep(0.3)


def send_message(message: str, dry_run: bool = False) -> dict:
    """在当前 QQ 聊天窗口发送消息
    
    Args:
        message: 要发送的消息文本
        dry_run: True 则只输入不按回车发送
    
    Returns:
        操作结果
    """
    result = {"success": False, "message": message, "dry_run": dry_run}
    
    if not is_qq_running():
        log.error("QQ 未运行")
        result["error"] = "QQ 未运行"
        return result
    
    activate_qq()
    time.sleep(0.3)
    
    # 截图记录发送前状态
    take_screenshot(filename="before_send.png")
    
    # 点击输入框区域（QQ 聊天窗口底部）
    win_info = get_qq_window_info()
    if win_info:
        # 点击输入框（通常在窗口底部 1/4 处）
        input_x = win_info["x"] + win_info["width"] // 2
        input_y = win_info["y"] + int(win_info["height"] * 0.85)
        pyautogui.click(input_x, input_y)
        time.sleep(0.3)
    
    # 输入消息
    log.info(f"输入消息: {message[:50]}{'...' if len(message) > 50 else ''}")
    type_text_via_applescript(message)
    time.sleep(0.2)
    
    if dry_run:
        log.info("[DRY RUN] 消息已输入但未发送")
        take_screenshot(filename="dry_run_typed.png")
        result["success"] = True
        result["status"] = "typed_not_sent"
        return result
    
    # 按回车发送
    script = f'''
    tell application "System Events"
        tell process "{QQ_APP_NAME}"
            key code 36
        end tell
    end tell
    '''
    run_applescript(script)
    time.sleep(0.5)
    
    # 截图记录发送后状态
    take_screenshot(filename="after_send.png")
    
    log.info("消息已发送")
    result["success"] = True
    result["status"] = "sent"
    return result


def search_contact(name: str) -> dict:
    """搜索联系人/群聊并打开对话
    
    Args:
        name: 联系人或群聊名称
    
    Returns:
        操作结果
    """
    result = {"success": False, "name": name}
    
    if not is_qq_running():
        log.error("QQ 未运行")
        result["error"] = "QQ 未运行"
        return result
    
    activate_qq()
    time.sleep(0.5)
    
    # Command+F 打开搜索（QQ macOS 的搜索快捷键）
    script = f'''
    tell application "System Events"
        tell process "{QQ_APP_NAME}"
            keystroke "f" using command down
        end tell
    end tell
    '''
    run_applescript(script)
    time.sleep(0.5)
    
    # 输入搜索内容
    log.info(f"搜索联系人: {name}")
    type_text_via_applescript(name)
    time.sleep(1)
    
    # 截图搜索结果
    take_screenshot(filename="search_result.png")
    
    # 按回车选择第一个结果
    script = f'''
    tell application "System Events"
        tell process "{QQ_APP_NAME}"
            key code 36
        end tell
    end tell
    '''
    run_applescript(script)
    time.sleep(0.5)
    
    take_screenshot(filename="after_search_select.png")
    
    log.info(f"已搜索并选择: {name}")
    result["success"] = True
    return result


# ============================================================
# 主入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="QQ 自动回复 Skill (macOS)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python3 qq_auto.py open                         # 激活 QQ
  python3 qq_auto.py read                         # 截取当前聊天截图
  python3 qq_auto.py list                         # 截取会话列表
  python3 qq_auto.py search --name "张三"         # 搜索联系人
  python3 qq_auto.py reply --message "你好！"     # 发送消息
  python3 qq_auto.py reply --message "测试" --dry-run  # 只输入不发送
        """
    )
    
    sub = parser.add_subparsers(dest="command", help="可用命令")
    
    # open 命令
    sub.add_parser("open", help="启动/激活 QQ 窗口")
    
    # read 命令
    p_read = sub.add_parser("read", help="截取当前 QQ 聊天窗口截图")
    p_read.add_argument("--output", "-o", help="输出文件名")
    
    # list 命令
    sub.add_parser("list", help="截取 QQ 会话列表截图")
    
    # search 命令
    p_search = sub.add_parser("search", help="搜索联系人/群聊")
    p_search.add_argument("--name", required=True, help="要搜索的联系人/群聊名称")
    
    # reply 命令
    p_reply = sub.add_parser("reply", help="在当前聊天窗口发送消息")
    p_reply.add_argument("--message", "-m", required=True, help="要发送的消息内容")
    p_reply.add_argument("--dry-run", action="store_true", help="只输入不发送")
    
    args = parser.parse_args()
    
    if args.command == "open":
        if is_qq_running():
            log.info("QQ 已在运行，激活窗口")
            activate_qq()
        else:
            log.info("启动 QQ...")
            launch_qq()
        take_screenshot(filename="qq_activated.png")
        log.info("QQ 已激活")
    
    elif args.command == "read":
        log.info("截取 QQ 聊天窗口...")
        path = screenshot_qq_window(filename=args.output if hasattr(args, 'output') and args.output else None)
        if path:
            print(f"截图路径: {path}")
    
    elif args.command == "list":
        log.info("截取 QQ 会话列表...")
        activate_qq()
        time.sleep(0.3)
        # 确保在消息列表页面（Cmd+1 切换到消息）
        script = f'''
        tell application "System Events"
            tell process "{QQ_APP_NAME}"
                keystroke "1" using command down
            end tell
        end tell
        '''
        run_applescript(script)
        time.sleep(0.5)
        path = screenshot_qq_window(filename="qq_list.png")
        if path:
            print(f"截图路径: {path}")
    
    elif args.command == "search":
        result = search_contact(args.name)
        if result["success"]:
            log.info(f"搜索完成: {args.name}")
        else:
            log.error(f"搜索失败: {result.get('error', '未知错误')}")
            sys.exit(1)
    
    elif args.command == "reply":
        result = send_message(args.message, dry_run=args.dry_run)
        if result["success"]:
            status = "已输入（未发送）" if args.dry_run else "已发送"
            log.info(f"消息{status}")
        else:
            log.error(f"发送失败: {result.get('error', '未知错误')}")
            sys.exit(1)
        
        # 保存操作记录
        report_path = LOG_DIR / f"reply_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
    
    else:
        parser.print_help()
        print("\n快速开始:")
        print("  python3 qq_auto.py open            # 激活 QQ")
        print("  python3 qq_auto.py read            # 截取聊天窗口")
        print("  python3 qq_auto.py search --name '张三'  # 搜索联系人")
        print("  python3 qq_auto.py reply -m '你好'  # 发送消息")


if __name__ == "__main__":
    main()
