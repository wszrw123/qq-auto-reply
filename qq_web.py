#!/usr/bin/env python3
"""
QQ 自动回复 Skill — 基于 QQ Web + Playwright（macOS）
通过 Playwright persistent context 操控 QQ 网页版，实现消息读取与回复。

功能：
  1. login   — 打开 QQ 网页版，扫码登录（persistent context 自动保持登录）
  2. read    — 截取当前聊天窗口截图，供 agent 分析消息内容
  3. search  — 搜索联系人/群聊并打开对话
  4. reply   — 在当前聊天窗口输入文字并发送
  5. list    — 截取 QQ 会话列表截图

使用方式：
  python3 qq_web.py login                          # 首次扫码登录
  python3 qq_web.py read                           # 截取当前聊天窗口
  python3 qq_web.py search --name "find!"          # 搜索并打开联系人
  python3 qq_web.py reply --message "你好！"       # 发送消息
  python3 qq_web.py reply --message "内容" --dry-run  # 只输入不发送

依赖：
  pip install playwright && playwright install chromium
"""

import argparse
import asyncio
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("缺少依赖: pip install playwright && playwright install chromium")
    sys.exit(1)

# ============================================================
# 配置
# ============================================================

SKILL_DIR = Path(__file__).parent
BROWSER_DATA_DIR = SKILL_DIR / "browser_data"
SCREENSHOT_DIR = SKILL_DIR / "screenshots"
LOG_DIR = SKILL_DIR / "logs"

for d in [BROWSER_DATA_DIR, SCREENSHOT_DIR, LOG_DIR]:
    d.mkdir(exist_ok=True)

QQ_WEB_URL = "https://im.qq.com/index/"
QQ_LOGIN_URL = "https://im.qq.com/index/"

# 日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_DIR / "qq_web.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)


# ============================================================
# QQ Web 自动化类
# ============================================================

class QQWebAutomation:
    def __init__(self, headless=False):
        self.headless = headless
        self.playwright = None
        self.context = None
        self.page = None

    async def start(self):
        """启动浏览器（persistent context）"""
        self.playwright = await async_playwright().start()
        self.context = await self.playwright.chromium.launch_persistent_context(
            user_data_dir=str(BROWSER_DATA_DIR),
            headless=self.headless,
            viewport={"width": 1280, "height": 900},
            locale="zh-CN",
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
        )
        if self.context.pages:
            self.page = self.context.pages[0]
        else:
            self.page = await self.context.new_page()
        log.info("浏览器已启动")

    async def stop(self):
        """关闭浏览器"""
        if self.context:
            await self.context.close()
        if self.playwright:
            await self.playwright.stop()
        log.info("浏览器已关闭（登录状态已持久化）")

    async def screenshot(self, name: str) -> str:
        """截取当前页面截图"""
        ts = datetime.now().strftime("%H%M%S")
        path = SCREENSHOT_DIR / f"{name}_{ts}.png"
        await self.page.screenshot(path=str(path))
        log.info(f"截图: {path.name}")
        return str(path)

    async def navigate_to_qq(self):
        """导航到 QQ 网页版"""
        current = self.page.url
        if "qq.com" not in current:
            log.info(f"导航到 QQ 网页版: {QQ_WEB_URL}")
            await self.page.goto(QQ_WEB_URL, wait_until="domcontentloaded", timeout=30000)
            await self.page.wait_for_timeout(2000)

    async def check_login(self) -> bool:
        """检查是否已登录"""
        try:
            # QQ 网页版登录后通常会有聊天列表或用户头像
            # 检查多个可能的已登录标识
            selectors = [
                ".recent-chat-list",
                ".chat-list",
                ".sidebar",
                "[class*='avatar']",
                "[class*='contact']",
                "[class*='session']",
            ]
            for sel in selectors:
                try:
                    el = await self.page.wait_for_selector(sel, timeout=2000)
                    if el:
                        log.info(f"已检测到登录状态 (选择器: {sel})")
                        return True
                except:
                    continue
            return False
        except:
            return False

    async def wait_for_login(self, timeout=300):
        """等待用户扫码登录"""
        log.info(f"请在浏览器中扫码登录 QQ（{timeout}秒超时）...")
        start = time.time()
        while time.time() - start < timeout:
            if await self.check_login():
                log.info("登录成功！")
                return True
            # 也检查 URL 变化（登录后可能跳转）
            if "web" in self.page.url or "chat" in self.page.url:
                await self.page.wait_for_timeout(2000)
                if await self.check_login():
                    log.info("登录成功！")
                    return True
            await self.page.wait_for_timeout(3000)
        log.error("登录超时")
        return False

    async def login(self):
        """执行登录流程"""
        await self.navigate_to_qq()
        await self.screenshot("login_page")

        if await self.check_login():
            log.info("已处于登录状态，无需重新登录")
            return True

        # 等待扫码登录
        return await self.wait_for_login()

    async def read_chat(self) -> str:
        """截取当前聊天窗口"""
        await self.navigate_to_qq()
        path = await self.screenshot("chat_window")
        log.info(f"聊天窗口截图: {path}")
        return path

    async def read_list(self) -> str:
        """截取会话列表"""
        await self.navigate_to_qq()
        path = await self.screenshot("session_list")
        log.info(f"会话列表截图: {path}")
        return path

    async def search_contact(self, name: str) -> dict:
        """搜索联系人/群聊并打开对话"""
        result = {"success": False, "name": name}

        await self.navigate_to_qq()
        await self.screenshot("before_search")

        # 尝试多个搜索框选择器
        search_selectors = [
            "input[placeholder*='搜索']",
            "input[type='search']",
            ".search-input input",
            "[class*='search'] input",
            "input[placeholder*='Search']",
        ]

        search_input = None
        for sel in search_selectors:
            try:
                search_input = await self.page.wait_for_selector(sel, timeout=3000)
                if search_input:
                    log.info(f"找到搜索框: {sel}")
                    break
            except:
                continue

        if not search_input:
            log.error("未找到搜索框")
            await self.screenshot("search_not_found")
            result["error"] = "未找到搜索框"
            return result

        await search_input.click()
        await search_input.fill(name)
        await self.page.wait_for_timeout(1500)
        await self.screenshot("search_results")

        # 点击第一个搜索结果
        result_selectors = [
            f"text={name}",
            ".search-result-item:first-child",
            "[class*='search-result'] >> nth=0",
        ]

        for sel in result_selectors:
            try:
                result_el = await self.page.wait_for_selector(sel, timeout=3000)
                if result_el:
                    await result_el.click()
                    await self.page.wait_for_timeout(1000)
                    log.info(f"已打开对话: {name}")
                    await self.screenshot("chat_opened")
                    result["success"] = True
                    return result
            except:
                continue

        log.warning(f"未找到搜索结果: {name}")
        result["error"] = "未找到搜索结果"
        return result

    async def send_message(self, message: str, dry_run: bool = False) -> dict:
        """在当前聊天窗口发送消息"""
        result = {"success": False, "message": message, "dry_run": dry_run}

        await self.navigate_to_qq()

        # 尝试多个输入框选择器
        input_selectors = [
            "[contenteditable='true']",
            ".chat-input [contenteditable]",
            "[class*='editor'] [contenteditable]",
            "div[role='textbox']",
            ".ql-editor",
            "textarea",
        ]

        msg_input = None
        for sel in input_selectors:
            try:
                msg_input = await self.page.wait_for_selector(sel, timeout=3000)
                if msg_input:
                    log.info(f"找到输入框: {sel}")
                    break
            except:
                continue

        if not msg_input:
            log.error("未找到消息输入框")
            await self.screenshot("input_not_found")
            result["error"] = "未找到消息输入框"
            return result

        # 点击输入框并输入消息
        await msg_input.click()
        await self.page.wait_for_timeout(200)

        # 使用 keyboard.type 输入（支持中文）
        await msg_input.fill("")  # 清空
        await self.page.keyboard.type(message, delay=30)
        await self.page.wait_for_timeout(300)

        log.info(f"已输入消息: {message[:50]}{'...' if len(message) > 50 else ''}")
        await self.screenshot("message_typed")

        if dry_run:
            log.info("[DRY RUN] 消息已输入但未发送")
            result["success"] = True
            result["status"] = "typed_not_sent"
            return result

        # 按 Enter 发送
        await self.page.keyboard.press("Enter")
        await self.page.wait_for_timeout(1000)

        await self.screenshot("message_sent")
        log.info("消息已发送")
        result["success"] = True
        result["status"] = "sent"
        return result


# ============================================================
# 主入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="QQ 自动回复 Skill — QQ Web + Playwright (macOS)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python3 qq_web.py login                          # 扫码登录
  python3 qq_web.py read                           # 截取当前聊天截图
  python3 qq_web.py list                           # 截取会话列表
  python3 qq_web.py search --name "find!"          # 搜索联系人
  python3 qq_web.py reply --message "你好！"       # 发送消息
  python3 qq_web.py reply --message "测试" --dry-run  # 只输入不发送
        """
    )

    sub = parser.add_subparsers(dest="command", help="可用命令")

    # login 命令
    sub.add_parser("login", help="扫码登录 QQ 网页版")

    # read 命令
    sub.add_parser("read", help="截取当前 QQ 聊天窗口截图")

    # list 命令
    sub.add_parser("list", help="截取 QQ 会话列表截图")

    # search 命令
    p_search = sub.add_parser("search", help="搜索联系人/群聊")
    p_search.add_argument("--name", required=True, help="联系人/群聊名称")

    # reply 命令
    p_reply = sub.add_parser("reply", help="在当前聊天窗口发送消息")
    p_reply.add_argument("--message", "-m", required=True, help="消息内容")
    p_reply.add_argument("--dry-run", action="store_true", help="只输入不发送")

    # headless 全局参数
    parser.add_argument("--headless", action="store_true", help="无头模式")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        print("\n快速开始:")
        print("  python3 qq_web.py login             # 首次扫码登录")
        print("  python3 qq_web.py read              # 截取聊天窗口")
        print("  python3 qq_web.py search --name 'find!'  # 搜索联系人")
        print("  python3 qq_web.py reply -m '你好'    # 发送消息")
        return

    async def run():
        bot = QQWebAutomation(headless=args.headless)
        try:
            await bot.start()

            if args.command == "login":
                success = await bot.login()
                if success:
                    log.info("登录完成，浏览器数据已保存到 browser_data/")
                else:
                    log.error("登录失败")
                    sys.exit(1)

            elif args.command == "read":
                path = await bot.read_chat()
                print(f"截图路径: {path}")

            elif args.command == "list":
                path = await bot.read_list()
                print(f"截图路径: {path}")

            elif args.command == "search":
                result = await bot.search_contact(args.name)
                if result["success"]:
                    log.info(f"搜索完成: {args.name}")
                else:
                    log.error(f"搜索失败: {result.get('error')}")
                    sys.exit(1)

            elif args.command == "reply":
                result = await bot.send_message(args.message, dry_run=args.dry_run)
                if result["success"]:
                    status = "已输入（未发送）" if args.dry_run else "已发送"
                    log.info(f"消息{status}")
                else:
                    log.error(f"发送失败: {result.get('error')}")
                    sys.exit(1)

                # 保存操作记录
                report = LOG_DIR / f"reply_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                with open(report, "w", encoding="utf-8") as f:
                    json.dump(result, f, indent=2, ensure_ascii=False)

        finally:
            await bot.stop()

    asyncio.run(run())


if __name__ == "__main__":
    main()
