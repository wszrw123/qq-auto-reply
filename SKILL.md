---
name: qq-auto-reply
description: QQ 桌面端自动回复技能（macOS）。通过 AppleScript + 截图实现 QQ 消息读取和自动回复。支持激活 QQ、截取聊天窗口、搜索联系人、发送消息。agent 通过截图分析消息内容，然后调用 reply 命令发送回复。
---

# QQ 自动回复技能（macOS）

通过 AppleScript + screencapture 自动化 macOS QQ 桌面端，实现消息读取和自动回复。

## 使用场景

- 用户需要自动回复 QQ 消息时
- 用户需要批量发送 QQ 消息时
- 用户需要监控 QQ 聊天记录时

## 前置条件

1. macOS 系统，已安装 QQ 桌面版（`/Applications/QQ.app`）
2. QQ 已登录
3. 系统偏好设置中已授予终端/IDE **辅助功能权限**（System Preferences → Privacy & Security → Accessibility）
4. Python 依赖：`pip install pyautogui pillow`

## 工作流程

### 第一步：激活 QQ

```bash
python3 qq_auto.py open
```

### 第二步：读取消息（截图）

```bash
# 截取当前聊天窗口
python3 qq_auto.py read

# 截取会话列表
python3 qq_auto.py list
```

截图保存在 `screenshots/` 目录，agent 通过查看截图分析消息内容。

### 第三步：搜索联系人（可选）

```bash
python3 qq_auto.py search --name "联系人名称"
```

### 第四步：发送回复

```bash
# 发送消息
python3 qq_auto.py reply --message "你好！"

# 试运行（只输入不发送）
python3 qq_auto.py reply --message "测试内容" --dry-run
```

## 命令参考

| 命令 | 说明 |
|------|------|
| `open` | 启动/激活 QQ 窗口 |
| `read` | 截取当前 QQ 聊天窗口截图 |
| `list` | 截取 QQ 会话列表截图 |
| `search --name <名称>` | 搜索联系人/群聊并打开对话 |
| `reply --message <内容>` | 在当前聊天窗口发送消息 |
| `reply --message <内容> --dry-run` | 只输入不发送（测试用） |
| `monitor -r <回复内容>` | 监听新消息并自动回复 |
| `monitor -t <联系人> -r <回复内容>` | 仅监听指定联系人 |

### monitor 参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--target, -t` | 仅监听指定联系人（包含匹配） | 所有联系人 |
| `--auto-reply, -r` | 自动回复内容，不指定则仅记录事件 | 无 |
| `--delay` | 回复延迟秒数 | 15 |
| `--jitter` | 延迟随机抖动范围±秒 | 5 |
| `--poll` | 轮询间隔秒数 | 5 |
| `--max-replies` | 最大回复次数，0=无限 | 0 |
| `--dry-run` | 只输入不发送 | false |

### 监听示例

```bash
# 监听所有消息，自动回复
python3 qq_auto.py monitor -r "稍等，马上回复你"

# 只监听 find! 的消息，10秒后回复
python3 qq_auto.py monitor -t "find!" -r "收到，稍后回复" --delay 10

# 只回复一次
python3 qq_auto.py monitor --max-replies 1 -r "在忙，稍后回复"

# 仅记录事件不回复（供 agent 处理）
python3 qq_auto.py monitor
```

### 检测机制

1. **窗口监控**：每5秒检查 QQ 窗口列表，新聊天窗口出现 = 有人找你
2. **Dock 徽章**：监控 QQ Dock 图标未读徽章数变化

### 回复延迟建议

- 默认 15秒 ± 5秒随机抖动（实际10~20秒），自然不显机器人
- 快速回复：`--delay 5 --jitter 2`（3~7秒）
- 慢速回复：`--delay 30 --jitter 10`（20~40秒）

## Agent 使用示例

当用户说"帮我回复 QQ 消息"时，agent 应：

1. `python3 qq_auto.py open` — 激活 QQ
2. `python3 qq_auto.py read` — 截取聊天窗口
3. 查看截图，分析对方发送的消息内容
4. 根据上下文组织回复内容
5. `python3 qq_auto.py reply --message "回复内容"` — 发送回复

当用户说"帮我给张三发 QQ 消息"时：

1. `python3 qq_auto.py open` — 激活 QQ
2. `python3 qq_auto.py search --name "张三"` — 搜索并打开对话
3. `python3 qq_auto.py reply --message "消息内容"` — 发送消息

## 目录结构

```
qq-auto-reply/
├── SKILL.md          # 本文件
├── qq_auto.py        # 核心自动化脚本
├── screenshots/      # 截图存放目录
└── logs/             # 操作日志 + 发送记录
```

## 注意事项

1. **辅助功能权限**：首次使用需在系统设置中授予辅助功能权限，否则 AppleScript 无法控制 QQ
2. **中文输入**：通过剪贴板粘贴实现，会覆盖当前剪贴板内容
3. **窗口焦点**：发送消息前会自动激活 QQ 窗口，确保 QQ 不在最小化状态
4. **安全**：建议先用 `--dry-run` 测试，确认无误后再实际发送
5. **QQ 版本**：适配 macOS QQ 桌面版，不支持 QQ NT 网页版
