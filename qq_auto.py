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
import random
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


def get_qq_window_info(window_name=None) -> dict:
    """获取 QQ 窗口的位置和大小
    
    Args:
        window_name: 指定窗口名称，None 则尝试获取主面板 "QQ" 窗口，
                     找不到则返回 front window
    """
    if window_name:
        script = f'''
        tell application "System Events"
            tell process "{QQ_APP_NAME}"
                set w to window "{window_name}"
                set winPos to position of w
                set winSize to size of w
                set x to item 1 of winPos as integer
                set y to item 2 of winPos as integer
                set ww to item 1 of winSize as integer
                set hh to item 2 of winSize as integer
                return (x as text) & "|" & (y as text) & "|" & (ww as text) & "|" & (hh as text)
            end tell
        end tell
        '''
    else:
        # 优先找名为 "QQ" 的主面板窗口
        script = f'''
        tell application "System Events"
            tell process "{QQ_APP_NAME}"
                try
                    set w to window "QQ"
                on error
                    set w to front window
                end try
                set winPos to position of w
                set winSize to size of w
                set x to item 1 of winPos as integer
                set y to item 2 of winPos as integer
                set ww to item 1 of winSize as integer
                set hh to item 2 of winSize as integer
                return (x as text) & "|" & (y as text) & "|" & (ww as text) & "|" & (hh as text)
            end tell
        end tell
        '''
    result = run_applescript(script)
    if result:
        parts = result.split("|")
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

def check_accessibility() -> bool:
    """检查是否有辅助功能权限"""
    script = '''
    tell application "System Events"
        keystroke ""
    end tell
    '''
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True, text=True, timeout=5
    )
    return result.returncode == 0


def set_clipboard(text: str):
    """通过 pbcopy 设置剪贴板内容（不需要辅助功能权限）"""
    process = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
    process.communicate(text.encode("utf-8"))


def send_keystroke(key: str, modifiers: list = None):
    """发送按键事件
    
    优先使用 AppleScript，如果权限不足则提示用户。
    key: 按键名称或字符
    modifiers: 修饰键列表，如 ['command'], ['command', 'shift']
    """
    if modifiers and 'command' in modifiers:
        mod_str = ' using command down'
    else:
        mod_str = ''
    
    # 对于回车键使用 key code
    if key == 'return':
        script = f'''
        tell application "System Events"
            tell process "{QQ_APP_NAME}"
                key code 36{mod_str}
            end tell
        end tell
        '''
    else:
        script = f'''
        tell application "System Events"
            tell process "{QQ_APP_NAME}"
                keystroke "{key}"{mod_str}
            end tell
        end tell
        '''
    
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True, text=True, timeout=5
    )
    if result.returncode != 0 and "1002" in result.stderr:
        log.error("缺少辅助功能权限！请前往: 系统设置 → 隐私与安全性 → 辅助功能 → 添加当前终端/IDE")
        raise PermissionError("缺少辅助功能权限 (Accessibility permission)")
    return result.returncode == 0


def paste_text(text: str):
    """通过剪贴板粘贴文字（支持中文）"""
    set_clipboard(text)
    time.sleep(0.1)
    send_keystroke("v", modifiers=["command"])
    time.sleep(0.3)


def send_message(message: str, dry_run: bool = False) -> dict:
    """在当前 QQ 聊天窗口发送消息
    
    优先查找已打开的聊天窗口，点击其输入区域，粘贴消息并发送。
    
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
    
    # 查找已打开的聊天窗口
    chat_win = find_chat_window()
    if chat_win:
        log.info(f"使用聊天窗口: {chat_win['name']}")
        raise_window(chat_win["name"])
        time.sleep(0.3)
        # 点击聊天窗口的输入区域（底部约85%处）
        input_x = chat_win["x"] + chat_win["width"] // 2
        input_y = chat_win["y"] + int(chat_win["height"] * 0.85)
        pyautogui.click(input_x, input_y)
        time.sleep(0.3)
        result["chat_window"] = chat_win["name"]
    else:
        log.warning("未找到聊天窗口，尝试在当前焦点窗口发送")
        win_info = get_qq_window_info()
        if win_info:
            input_x = win_info["x"] + win_info["width"] // 2
            input_y = win_info["y"] + int(win_info["height"] * 0.85)
            pyautogui.click(input_x, input_y)
            time.sleep(0.3)
    
    # 输入消息
    log.info(f"输入消息: {message[:50]}{'...' if len(message) > 50 else ''}")
    try:
        paste_text(message)
    except PermissionError:
        result["error"] = "缺少辅助功能权限"
        return result
    time.sleep(0.2)
    
    if dry_run:
        log.info("[DRY RUN] 消息已输入但未发送")
        result["success"] = True
        result["status"] = "typed_not_sent"
        return result
    
    # 按回车发送
    try:
        send_keystroke("return")
    except PermissionError:
        result["error"] = "缺少辅助功能权限，消息已输入但无法发送"
        return result
    time.sleep(0.5)
    
    log.info("消息已发送")
    result["success"] = True
    result["status"] = "sent"
    return result


def get_qq_windows() -> list:
    """获取所有 QQ 窗口信息列表"""
    script = f'''
    tell application "System Events"
        tell process "{QQ_APP_NAME}"
            set winInfo to {{}}
            repeat with w in every window
                set wName to name of w
                set wPos to position of w
                set wSize to size of w
                set x to item 1 of wPos as integer
                set y to item 2 of wPos as integer
                set ww to item 1 of wSize as integer
                set hh to item 2 of wSize as integer
                set end of winInfo to wName & ":" & (x as text) & "|" & (y as text) & "|" & (ww as text) & "|" & (hh as text)
            end repeat
            set AppleScript's text item delimiters to ";;;"
            return winInfo as text
        end tell
    end tell
    '''
    result = run_applescript(script)
    windows = []
    if result:
        for item in result.split(";;;"):
            item = item.strip()
            if ":" in item:
                name, coords = item.split(":", 1)
                parts = coords.split("|")
                if len(parts) == 4:
                    windows.append({
                        "name": name.strip(),
                        "x": int(parts[0]),
                        "y": int(parts[1]),
                        "width": int(parts[2]),
                        "height": int(parts[3]),
                    })
    return windows


def find_chat_window() -> dict:
    """查找已打开的 QQ 聊天窗口（非主面板）"""
    windows = get_qq_windows()
    for w in windows:
        # 聊天窗口通常有联系人名称，且不叫 "QQ" 或 "全网搜索"
        if w["name"] and w["name"] not in ("", "QQ", "全网搜索"):
            return w
    return None


def raise_window(window_name: str):
    """将指定窗口提到最前"""
    script = f'''
    tell application "System Events"
        tell process "{QQ_APP_NAME}"
            perform action "AXRaise" of window "{window_name}"
        end tell
    end tell
    '''
    run_applescript(script)
    time.sleep(0.3)


def search_contact(name: str) -> dict:
    """搜索联系人/群聊并打开对话
    
    QQ NT 搜索流程：点击主面板搜索区域 → 粘贴名称 → 回车打开聊天窗口
    
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
    
    # 获取 QQ 主面板窗口位置
    win_info = get_qq_window_info()
    if not win_info:
        log.error("无法获取 QQ 窗口信息")
        result["error"] = "无法获取 QQ 窗口信息"
        return result
    
    # 点击搜索区域（QQ NT 主面板顶部搜索框）
    search_x = win_info["x"] + win_info["width"] // 2
    search_y = win_info["y"] + 70  # 搜索框通常在顶部约70px处
    log.info(f"点击搜索区域: ({search_x}, {search_y})")
    pyautogui.click(search_x, search_y)
    time.sleep(0.5)
    
    # 粘贴搜索内容
    log.info(f"搜索联系人: {name}")
    try:
        paste_text(name)
    except PermissionError:
        result["error"] = "缺少辅助功能权限"
        return result
    time.sleep(1)
    
    # 按回车选择第一个搜索结果（打开聊天窗口）
    try:
        send_keystroke("return")
    except PermissionError:
        result["error"] = "缺少辅助功能权限"
        return result
    time.sleep(1)
    
    # 检查是否打开了新的聊天窗口
    chat_win = find_chat_window()
    if chat_win:
        log.info(f"已打开聊天窗口: {chat_win['name']} ({chat_win['width']}x{chat_win['height']})")
        result["success"] = True
        result["chat_window"] = chat_win["name"]
    else:
        log.warning("未检测到新的聊天窗口，搜索可能未成功")
        result["success"] = True  # 仍然标记成功，因为操作已执行
        result["note"] = "操作已执行但未检测到聊天窗口"
    
    return result


# ============================================================
# 消息监听与自动回复
# ============================================================

EVENT_FILE = LOG_DIR / "new_message_events.jsonl"


def get_dock_badge() -> int:
    """获取 QQ Dock 图标未读徽章数"""
    script = '''
    tell application "System Events"
        tell process "Dock"
            try
                set dockItems to every UI element of list 1
                repeat with dockItem in dockItems
                    if name of dockItem is "QQ" then
                        try
                            set badgeText to value of attribute "AXStatusLabel" of dockItem
                            if badgeText is not "" and badgeText is not missing value then
                                return badgeText
                            end if
                        end try
                        return "0"
                    end if
                end repeat
            end try
            return "0"
        end tell
    end tell
    '''
    result = run_applescript(script)
    try:
        return int(result)
    except (ValueError, TypeError):
        return 0


def monitor_chat(
    target: str = None,
    auto_reply: str = None,
    delay: float = 15.0,
    jitter: float = 5.0,
    poll_interval: float = 5.0,
    max_replies: int = 0,
    dry_run: bool = False,
):
    """监听 QQ 消息并自动回复

    检测方式：
      1. 监控 QQ 窗口列表变化（新聊天窗口出现 = 有人找你）
      2. 监控 Dock 未读徽章数变化

    Args:
        target: 仅监听指定联系人的消息，None 则监听所有
        auto_reply: 自动回复内容，None 则只记录事件不回复
        delay: 回复延迟秒数（默认15秒）
        jitter: 延迟随机抖动范围（默认±5秒）
        poll_interval: 轮询间隔秒数（默认5秒）
        max_replies: 最大回复次数，0=无限
        dry_run: True 则只输入不发送
    """
    log.info("=" * 50)
    log.info("QQ 消息监听已启动")
    log.info(f"  监听目标: {target or '所有联系人'}")
    log.info(f"  自动回复: {'是' if auto_reply else '否（仅记录事件）'}")
    log.info(f"  回复延迟: {delay}s ± {jitter}s")
    log.info(f"  轮询间隔: {poll_interval}s")
    log.info(f"  最大回复: {max_replies or '无限'}")
    log.info(f"  Dry-run:  {dry_run}")
    log.info("=" * 50)
    log.info("按 Ctrl+C 停止监听\n")

    # 记录初始状态
    known_windows = set()
    for w in get_qq_windows():
        known_windows.add(w["name"])
    last_badge = get_dock_badge()
    reply_count = 0
    # 已回复的窗口（避免重复回复同一个人）
    replied_windows = set()

    try:
        while True:
            time.sleep(poll_interval)

            if not is_qq_running():
                log.warning("QQ 未运行，等待中...")
                continue

            # 检测 1: 新聊天窗口
            current_windows = {}
            for w in get_qq_windows():
                current_windows[w["name"]] = w
            current_names = set(current_windows.keys())
            new_windows = current_names - known_windows - {"", "QQ", "全网搜索"}

            # 检测 2: Dock 徽章变化
            current_badge = get_dock_badge()
            badge_increased = current_badge > last_badge

            if new_windows or badge_increased:
                if badge_increased:
                    log.info(f"📬 检测到未读消息变化: {last_badge} → {current_badge}")
                    last_badge = current_badge

                for win_name in new_windows:
                    if not win_name or win_name in ("QQ", "全网搜索"):
                        continue

                    # 如果指定了目标，只响应目标联系人
                    if target and target not in win_name:
                        log.info(f"  忽略非目标窗口: {win_name}")
                        continue

                    # 避免重复回复
                    if win_name in replied_windows:
                        log.info(f"  已回复过: {win_name}，跳过")
                        continue

                    log.info(f"📨 新消息来自: {win_name}")

                    # 记录事件
                    event = {
                        "timestamp": datetime.now().isoformat(),
                        "sender": win_name,
                        "type": "new_chat_window",
                        "replied": False,
                    }

                    if auto_reply:
                        # 计算实际延迟
                        actual_delay = max(1, delay + random.uniform(-jitter, jitter))
                        log.info(f"  ⏳ 等待 {actual_delay:.1f} 秒后回复...")
                        time.sleep(actual_delay)

                        # 确保窗口仍然存在
                        activate_qq()
                        time.sleep(0.3)

                        chat_win = None
                        for w in get_qq_windows():
                            if w["name"] == win_name:
                                chat_win = w
                                break

                        if chat_win:
                            raise_window(win_name)
                            time.sleep(0.3)
                            input_x = chat_win["x"] + chat_win["width"] // 2
                            input_y = chat_win["y"] + int(chat_win["height"] * 0.85)
                            pyautogui.click(input_x, input_y)
                            time.sleep(0.3)

                            try:
                                paste_text(auto_reply)
                                time.sleep(0.2)

                                if not dry_run:
                                    send_keystroke("return")
                                    time.sleep(0.5)
                                    log.info(f"  ✅ 已回复 {win_name}: {auto_reply[:30]}...")
                                    event["replied"] = True
                                    event["reply_message"] = auto_reply
                                else:
                                    log.info(f"  [DRY RUN] 已输入但未发送给 {win_name}")
                                    event["replied"] = False
                                    event["note"] = "dry_run"

                                replied_windows.add(win_name)
                                reply_count += 1

                            except PermissionError:
                                log.error("  缺少辅助功能权限")
                                event["error"] = "缺少辅助功能权限"
                        else:
                            log.warning(f"  窗口 {win_name} 已关闭，跳过回复")
                            event["error"] = "窗口已关闭"

                    # 写入事件文件
                    with open(EVENT_FILE, "a", encoding="utf-8") as f:
                        f.write(json.dumps(event, ensure_ascii=False) + "\n")

                    if max_replies and reply_count >= max_replies:
                        log.info(f"已达到最大回复次数 ({max_replies})，停止监听")
                        return

            # 更新已知窗口
            known_windows = current_names
            last_badge = current_badge

    except KeyboardInterrupt:
        log.info("\n监听已停止")
        log.info(f"共回复 {reply_count} 条消息")


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
  python3 qq_auto.py search --name "张三"         # 搜索联系人
  python3 qq_auto.py reply --message "你好！"     # 发送消息
  python3 qq_auto.py reply --message "测试" --dry-run  # 只输入不发送
  python3 qq_auto.py monitor -r "稍等，马上回复你"     # 监听并自动回复
  python3 qq_auto.py monitor -t "find!" -r "收到" --delay 10  # 指定联系人
  python3 qq_auto.py monitor --max-replies 1 -r "在忙，稍后回复"  # 只回复一次
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
    
    # monitor 命令
    p_mon = sub.add_parser("monitor", help="监听 QQ 消息并自动回复")
    p_mon.add_argument("--target", "-t", help="仅监听指定联系人（包含匹配），不指定则监听所有")
    p_mon.add_argument("--auto-reply", "-r", help="自动回复内容，不指定则仅记录事件")
    p_mon.add_argument("--delay", type=float, default=15.0, help="回复延迟秒数（默认15秒）")
    p_mon.add_argument("--jitter", type=float, default=5.0, help="延迟随机抖动范围±秒（默认5秒）")
    p_mon.add_argument("--poll", type=float, default=5.0, help="轮询间隔秒数（默认5秒）")
    p_mon.add_argument("--max-replies", type=int, default=0, help="最大回复次数，0=无限（默认0）")
    p_mon.add_argument("--dry-run", action="store_true", help="只输入不发送")
    
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
        try:
            send_keystroke("1", modifiers=["command"])
        except PermissionError:
            log.error("缺少辅助功能权限")
            sys.exit(1)
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
    
    elif args.command == "monitor":
        monitor_chat(
            target=args.target,
            auto_reply=args.auto_reply,
            delay=args.delay,
            jitter=args.jitter,
            poll_interval=args.poll,
            max_replies=args.max_replies,
            dry_run=args.dry_run,
        )
    
    else:
        parser.print_help()
        print("\n快速开始:")
        print("  python3 qq_auto.py open            # 激活 QQ")
        print("  python3 qq_auto.py search --name '张三'  # 搜索联系人")
        print("  python3 qq_auto.py reply -m '你好'  # 发送消息")
        print("  python3 qq_auto.py monitor -r '稍等，马上回复你'  # 自动回复")
        print("  python3 qq_auto.py monitor -t 'find!' -r '收到' --delay 10  # 指定联系人")


if __name__ == "__main__":
    main()
