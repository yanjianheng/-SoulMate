# 任务归档与技术决策

> 📎 本文件为【只追加】文件。AI 只能在文件顶部追加新记录，禁止修改或删除已有内容。
> 本文件是项目的"永久知识库"，接收两类信息：
> 1. **任务归档**：active.md 覆写前，将实现思路、边界条件、经验教训归档到这里
> 2. **技术决策**：Bug 根因分析、技术选型论证、架构决策记录
>
> 倒序排列：最新的记录在最前面。
> 重要的通用经验应提炼后手动写入 rules/xxx.md。

---

## [2026-04-10] Bug 根因分析：里程碑1 联调三连坑

### 📋 类型：Bug 根因分析

### ❓ 问题一：`ModuleNotFoundError: No module named 'app'`

**现象**：`voice_main.py` 被放到 `project/app/voice/` 目录下运行时，找不到 `app` 模块。  
**根因**：`sys.path.insert(0, str(Path(__file__).parent / "project"))` 这行代码是按照"文件放在项目根目录"写的，移动文件后 `.parent` 只往上退一级，实际路径已经错了。  
**解决**：改为 `Path(__file__).parent.parent.parent`（从 `app/voice/` 向上跳三级回到 `project/`），同时相应把 `from voice.xxx` 改为 `from app.voice.xxx`。  
**教训**：`__file__` 的 `.parent` 级数必须与文件实际所在层级严格对应，文件移动后第一件事是检查路径跳级数量。

---

### ❓ 问题二：`RuntimeError: Library cublas64_12.dll is not found`

**现象**：`faster-whisper` 在调用 GPU 推理时崩溃，找不到 CUDA 12 的运算加速库 `cublas64_12.dll`。  
**根因**：`stt.py` 使用了 `device="cuda"` + `compute_type="float16"`，但系统未安装 CUDA 12 工具包（或路径未配置）。  
**解决（临时方案）**：改为 `device="cpu"` + `compute_type="int8"`，牺牲约 1-2 秒推理速度，彻底绕过驱动依赖。STT 耗时从崩溃变为正常的 3-4 秒。  
**教训**：Windows 下 CUDA 环境极易因版本不对齐而静默失效。在 GPU 环境稳定之前，永远先用 CPU 模式跑通闭环，再逐步升级。

---

### ❓ 问题三：`ollama._types.ResponseError: (status code: 502)`

**现象**：调用本地 Ollama `http://localhost:11434/api/chat` 时持续返回 502 Bad Gateway，但直接用 `Invoke-RestMethod` 访问该端口完全正常。  
**根因**：Python `requests` 库默认会读取系统 HTTP_PROXY / HTTPS_PROXY 环境变量。Windows 上若配置了 VPN 或代理，requests 会把发往 `localhost` 的请求也转发给代理服务器，代理无法路由到本地端口，故返回 502。  
**解决**：在 `requests.post()` 调用处加入 `proxies={"http": None, "https": None}`，强制绕过代理直连本地。  
**附加坑**：`ollama` Python 库 v0.6.1 本身也可能存在兼容问题（返回值解析），最终彻底放弃 `ollama` 库，改为直接用 `requests` 调用 REST API，`stream=False`，解析 `message.content` 字段。  
**教训**：本地服务调用要**永远加 `proxies={"http": None, "https": None}`**，这是 Windows 开发环境的标准防御写法。`ollama` Python 库版本更新较快，接口调用方式可能随版本变动，优先考虑直接 HTTP 调用。

---

### ❓ 问题四：`pygame.error: Bad WAV file (no DATA chunk)`

**现象**：TTS 合成后播放时 pygame 报 WAV 文件损坏。  
**根因**：`generate_reply()` 因 Ollama 502 失败，返回空字符串 `""`。空字符串被传给 MeloTTS，MeloTTS 生成了一个只有头没有音频数据的损坏 WAV 文件，pygame 无法播放。  
**解决**：在 `tts.py` 的 `text_to_speech()` 入口加空文本检查（`if not text: return ""`），在 `voice_main.py` 中加双重守卫：`reply` 为空则 `continue`，`audio_file` 为空则 `continue`，避免任一环节失败后程序崩溃。  
**教训**：任何 AI 推理函数都可能返回空值，下游消费前必须做空值保护，严禁裸调用。

---

### 📌 整体经验教训
- Windows 开发环境的"隐形坑"特别多（代理、CUDA、文件权限），要养成每次改环境后先跑最小闭环测试的习惯。
- 一次联调暴露多个坑时，要逐个隔离解决，不要同时改多处。
- 程序的鲁棒性守则：每个返回值都可能是空/异常，核心路径上的每个环节都要有明确的 fallback 或 continue 处理。

### 📁 涉及文件
- `project/app/voice/voice_main.py`（路径修复、安全守卫）
- `project/app/voice/stt.py`（CPU 降级）
- `project/app/voice/tts.py`（空文本保护）
- `project/app/chat/engine.py`（requests 直调 + 代理绕过）

---



### 📋 类型：架构决策

### ❓ 问题现象 / 背景
当前仓库已经积累了 `dataBank/` 下 33 份非 `.ai` Markdown 文档，覆盖导航、项目进度、路线规划、环境教程、源码讲解、测试发布与运维；同时 `project/.ai/` 仍处于模板初始状态。  
如果后续 AI 每次都重新全量扫描全部文档与代码，一方面成本高，另一方面容易因为会话差异造成关注点不一致，无法形成稳定的“项目工作记忆”。

### 🔍 根因分析 / 方案对比

| 维度 | 方案 A：把 `dataBank/` 内容大段复制进 `.ai` | 方案 B：把 `.ai` 作为压缩后的操作性记忆层 |
|------|--------|--------|
| 优点 | 信息看似完整，短期内不需要再总结 | 体量小、检索快、适合后续 AI 协作与持续维护 |
| 缺点 | 内容重复、易过时、污染模板、后续维护成本高 | 首轮需要人工/AI 做归纳与结构化抽取 |

### ✅ 最终决策
采用方案 B：`dataBank/` 继续作为人工文档母本，`project/.ai/` 只沉淀高频、稳定、便于执行的项目记忆。  
首轮初始化时允许对 `rules/` 做一次填充；首轮完成后，`rules/` 默认回到只读层，新增经验优先进入 `logs/archive.md`，当前状态进入 `context/active.md`，阶段进度进入 `context/progress.md`。

### 🔧 实现要点
1. 先读取 `.ai/SYSTEM_PROMPT.md` 与 `.ai/README.md`，以模板协议而不是个人习惯为准。
2. 对现有 Markdown 按目录归类，总结为导航/进度/路线/教程/源码讲解/运维六类信息，再结合真实代码结构抽取稳定事实。
3. `rules/global.md` 只保留项目全局规范、架构、目录、技术栈、禁忌与依赖，不复制大段原文。
4. `context/active.md` 记录当前正在做的任务快照；`context/progress.md` 记录阶段化进度；两个文件允许后续覆写。
5. `logs/archive.md` 与 `logs/changelog.md` 均采用顶部追加，保留时间顺序与审计痕迹。

### 📌 经验教训
- `.ai` 不是第二套文档库，而是给 AI 使用的“最小但够用”的操作记忆层。
- 首轮写入 `rules/` 时要尽量抽取稳定规则，避免把短期任务状态写进只读规范。
- 后续若 `dataBank/` 增长很快，应优先更新 `context` 与 `logs`，只有跨任务长期稳定的内容才回灌到 `rules/`。

---

<!--
=== 任务归档模板 ===

## [YYYY-MM-DD] 任务归档：[任务名称]

### 📋 类型：任务归档
### 🎯 任务目标
[这个任务要完成什么]

### 💡 实现思路（永久保存）
1. [步骤1]
2. [步骤2]
3. [步骤3]

### 🔐 边界条件（永久保存）
- [边界1：如何处理的]
- [边界2：如何处理的]

### ✅ 验证结果
- [编译/测试是否通过]
- [发现了什么问题]

### 📌 经验教训
- [以后需要注意什么]

### 📁 涉及文件
- [文件路径]

---
-->

<!--
=== 技术决策模板 ===

## [YYYY-MM-DD] [问题/决策标题]

### 📋 类型：[Bug根因分析 / 技术选型 / 架构决策 / 性能优化]

### ❓ 问题现象 / 背景
[描述]

### 🔍 根因分析 / 方案对比

| 维度 | 方案 A | 方案 B |
|------|--------|--------|
| 优点 | | |
| 缺点 | | |

### ✅ 最终决策
[采用了什么，为什么]

### 🔧 实现要点
[关键细节]

### 📌 经验教训
[启示]

---
-->
