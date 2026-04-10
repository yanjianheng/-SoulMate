# 项目全局规范

> ⚠️ 本文件为【只读】文件，AI 只能读取参考，不能修改。
> 所有修改由开发者本人手动完成。

---

## 一、项目概述

**项目名称：** SoulMate
**一句话描述：** 面向 Windows 主线的本地 AI 伴侣原型，当前优先稳住 CLI 文本对话、会话记忆、数据可追溯与可恢复，再逐步接入语音、长期记忆、工具调用和表情交互。
**项目状态：** 开发中（Windows 文本主链路已落地，语音/长期记忆/Agent/UI 处于规划与分阶段落地中）
**开发人员：** [待确认]

---

## 二、技术栈

| 类别 | 技术选型 | 版本 |
|------|---------|------|
| 编程语言 | Python | 3.10.x（主线推荐固定） / 3.11（语音路线文档候选） |
| 框架 | Python 标准库 CLI + Ollama Python SDK | 当前无重量 Web/UI 框架 |
| 编译器/运行时 | CPython + PowerShell + `.venv` | Windows 主线 |
| 目标平台 | Windows 11（主线），WSL 仅可选调试 | |
| 通信协议 | 本机 HTTP（Ollama API `http://127.0.0.1:11434`） | |
| 数据库/存储 | SQLite（`project/data/app.db`） | |
| 版本控制 | Git | |
| 构建工具 | 无传统构建系统；通过 `python -m` + PowerShell 脚本运行 | `project/scripts/` |

---

## 三、系统架构

### 3.1 整体分层

```
┌──────────────────────────┐
│ CLI / 交互入口层          │  `project/app/main.py`，未来扩展 `voice_main.py`
├──────────────────────────┤
│ 会话与业务编排层          │  参数解析、命令处理、会话选择、上下文组装
├──────────────────────────┤
│ 模型适配与本地服务层      │  `app/chat/engine.py` -> Ollama 本机服务
├──────────────────────────┤
│ 数据存储与运维支撑层      │  SQLite、初始化脚本、smoke/backup 脚本、文档体系
└──────────────────────────┘
```

### 3.2 核心模块说明

| 模块 | 主要文件 | 职责 |
|------|---------|------|
| 入口与流程调度 | `project/app/main.py` | 解析命令行参数、选择用户和会话、处理 `/help` `/history` `/sessions` `/new` `/switch` `/title` 等命令，并协调模型调用与消息落库 |
| 模型调用适配 | `project/app/chat/engine.py` | 封装 `ollama.chat` 调用，隔离 SDK 导入和返回格式差异，保证非聊天路径不被模型依赖拖死 |
| 数据存储与 Schema | `project/app/db/sqlite_store.py`、`project/init_db.py`、`project/data/app.db` | 管理数据库路径、连接、建表、users/sessions/messages 三张表及其 CRUD 逻辑 |
| 脚本与运维辅助 | `project/scripts/smoke_test.ps1`、`project/scripts/backup_soulmate.ps1`、`project/scripts/smoke_test.sh`、`project/scripts/dev_enter.sh` | 提供冒烟测试、备份恢复、进入开发环境等命令级辅助能力 |
| 文档与知识体系 | `dataBank/` | 维护导航、环境教程、路线规划、源码讲解、测试发布与运维知识，作为 `.ai` 的人工文档母本 |

### 3.3 目录结构

```
项目根目录/
├── dataBank/         人工文档库（导航、路线、教程、源码讲解、测试运维）
└── project/
    ├── .ai/          AI 记忆系统
    ├── app/
    │   ├── chat/
    │   └── db/
    ├── data/
    ├── scripts/
    ├── init_db.py
    └── requirements.txt
```

---

## 四、全局编码规范

### 4.1 命名规则

| 类型 | 规则 | 示例 |
|------|------|------|
| 类名 | 大驼峰 | `ChatRuntime` |
| 函数名 | snake_case | `get_recent_messages` |
| 变量名 | snake_case | `session_id` |
| 常量 | 全大写下划线 | `SYSTEM_PROMPT` |

### 4.2 编码约定

- 程序统一从 `project` 根目录进入虚拟环境后执行，Windows 主线优先 `python -m app.main`。
- 流程编排留在 `app/main.py`，模型适配逻辑留在 `app/chat/engine.py`，SQL 与建表逻辑留在 `app/db/sqlite_store.py`。
- 数据结构变更必须先备份 `project/data/app.db`，再通过可重复脚本和验收 SQL 完成迁移，不直接手工多次修改数据库。
- 关键改动后同步更新 `dataBank/01_项目进度/改动日志.md`，并按测试与发布清单执行最小回归和发布 Gate。
- Windows 是唯一主运行环境；路径优先使用默认规则或环境变量（如 `SOULMATE_DB_PATH`），避免 Windows / WSL 路径混用。

### 4.3 禁止事项

- 禁止 Windows 与 WSL 同时读写同一个 `project/data/app.db`。
- 禁止把 SQL 语句、模型 SDK 细节或未来工具逻辑直接散落到 `app/main.py`。
- 禁止在未备份数据库的情况下直接修改表结构或手工改动关键业务数据。
- 禁止发布前跳过 `smoke_test.ps1`、数据一致性 SQL 检查和发布前检查清单。

---

## 五、第三方依赖

| 库名 | 用途 | 备注 |
|------|------|------|
| `ollama` | 通过 Python 调用本机 Ollama 模型服务 | 当前 `requirements.txt` 中的唯一必需第三方 Python 依赖 |
| Ollama Desktop / Service | 本地运行 `qwen3:8b-q4_K_M` 等模型 | Windows 主线环境建议固定 `http://127.0.0.1:11434` |
| SQLite / `sqlite3` | 会话、消息和未来长期记忆的单库存储 | 当前主线三张表为 `users` / `sessions` / `messages` |
| DB Browser for SQLite / sqlite3 CLI | 数据库可视化检查与 SQL 验收 | 运维辅助工具，不是运行时强依赖 |
| PowerShell 脚本 | 冒烟测试、备份恢复、进入环境 | 主要位于 `project/scripts/` |
| `faster-whisper`、`sounddevice`、`pygame`、`silero-vad`、`PyQt6` | 语音识别、音频 I/O、VAD、表情 UI | 目前属于里程碑文档中的规划依赖，尚未全部落到主分支代码 |
