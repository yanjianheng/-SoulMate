# 每日工作变更日志

> 📎 本文件为【只追加】文件。AI 只能在文件顶部追加新记录，禁止修改或删除已有内容。
> 倒序排列：最新的记录在最前面。

---

## 2026-04-10 [星期四]

### 🔧 修复
- `voice_main.py`：修复因文件移动导致的 `sys.path` 跳级错误（`.parent` 从 1 级改为 3 级），`from voice.xxx` 统一修正为 `from app.voice.xxx`。
- `stt.py`：将 Whisper 从 `device="cuda"` 降级为 `device="cpu"` + `compute_type="int8"`，绕过 Windows 缺失 `cublas64_12.dll` 导致的崩溃。
- `engine.py`：彻底放弃 `ollama` Python 库（v0.6.1 在 Windows 代理环境下触发 502），改为直接用 `requests` 调用 Ollama REST API，并加入 `proxies={"http": None, "https": None}` 强制绕过系统代理。
- `tts.py`：在 `text_to_speech()` 入口加入空文本保护，防止 MeloTTS 接收空字符串后生成损坏的 WAV 文件。
- `voice_main.py`：加入双重空值守卫（`reply` 为空 → `continue`，`audio_file` 为空 → `continue`），任一环节失败不再崩溃，优雅降级重新进入下一轮录音。

### ✨ 新增
- `voice_main.py`：暂时注释掉临时音频文件的删除逻辑，保留 `project/data/audio_temp/` 中的 WAV 文件供调试回听。

### 📁 涉及文件
- `project/app/voice/voice_main.py`
- `project/app/voice/stt.py`
- `project/app/voice/tts.py`
- `project/app/chat/engine.py`

### 📝 备注
- 里程碑 1 语音闭环已联调通过，完整路径：录音 → Whisper STT → Ollama LLM → MeloTTS → pygame 播放。
- 下一步：开始里程碑 2（VAD 自动录音 + 流式推理 + 打断机制）。

---



### 🔧 修复
- 补齐 `.ai` 首轮初始化时缺失的进度与归档记录，避免后续 AI 只看到模板而无法继承当前项目状态。

### ✨ 新增
- 新增 `project/.ai/context/progress.md` 的阶段化进度内容，明确 Windows 文本主线、语音记忆路线与测试交付路线。
- 新增 `project/.ai/logs/archive.md` 的初始化架构决策记录，沉淀 `dataBank/` 到 `.ai` 的知识迁移原则。

### 🔄 变更
- 完成 `project/.ai/logs/changelog.md` 首条工作日志追加。
- 按用户授权完成 `project/.ai/rules/global.md` 的首次写入；后续默认按只读规则使用。
- 保持 `.ai` 模板框架不变，仅替换占位符或按协议在日志顶部追加内容。

### 📁 涉及文件
- `project/.ai/rules/global.md`
- `project/.ai/context/active.md`
- `project/.ai/context/progress.md`
- `project/.ai/logs/archive.md`
- `project/.ai/logs/changelog.md`

### 📝 备注
- 本次变更基于对 33 份非 `.ai` Markdown 文档和主线代码结构的归纳，不是原文复制。
- `rules/` 本轮属于首轮初始化写入；后续新增经验应优先沉淀到 `logs/archive.md`。

---

<!-- 
=== 追加模板 ===
每次追加时，复制以下模板到本注释下方：

## YYYY-MM-DD [星期X]

### 🔧 修复
- [修复了什么问题]（简述原因）

### ✨ 新增
- [新增了什么功能]

### 🔄 变更
- [修改了什么逻辑或配置]

### 📁 涉及文件
- [文件路径1]
- [文件路径2]

### 📝 备注
- [其他需要记录的事项]

---
-->
