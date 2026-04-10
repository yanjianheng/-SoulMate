# .ai 三层记忆协议 v4 — 使用指南

## 快速开始

### 1. 复制到新项目
```powershell
xcopy /E /I ".ai" "你的新项目路径\.ai"
```

### 2. 配置 AI 提示词
将 `SYSTEM_PROMPT.md` 内容复制到你的 AI 工具中：

| AI 工具 | 配置位置 |
|---------|---------|
| **Antigravity** | 用户全局规则 (User Rules) |
| **Codex CLI** | 系统提示词 / 项目配置 |
| **Cursor** | Settings → Rules for AI 或 `.cursorrules` |
| **Cline / Roo Code** | `.clinerules` |

### 3. 填写项目信息
1. `rules/global.md` → 项目框架、技术栈、架构、编码规范
2. `context/progress.md` → 功能拆分和阶段规划
3. 按需复制 `rules/_module_template.md` → 重命名为模块规范

---

## 文件结构

```
.ai/
├── SYSTEM_PROMPT.md              系统提示词（复制到AI工具配置中）
├── README.md                     本使用指南
│
├── 🔒 rules/                     只读层（人工维护，AI只读）
│   ├── global.md                 项目框架 + 技术栈 + 架构 + 编码规范
│   └── _module_template.md       模块规范模板（复制后重命名）
│
├── 📝 context/                   读写层（AI可覆写）
│   ├── active.md                 当前任务状态快照
│   └── progress.md               功能拆分 + 进度看板
│
└── 📎 logs/                      追加层（AI只追加，不改旧内容）
    ├── archive.md                任务归档 + 问题分析 + 技术决策
    └── changelog.md              每日工作变更日志
```

---

## 任务完整生命周期

```
① 计划          ② 执行          ③ 验证        ④ 归档          ⑤ 提炼
progress.md ──→ active.md ──→ 编译/测试 ──→ archive.md ──→ rules/xxx.md
(从这里领任务)  (状态快照)    (必须通过)    (永久知识库)    (手动提炼铁律)
                     │
                     ↓
               changelog.md
               (每日简报)
```

**一句话记住：** 计划→执行→验证→归档→提炼

---

## 信息归属速查表

| 你要记录的信息 | 放在哪个文件 | 放在哪个章节 |
|:---|:---|:---|
| 项目框架/系统架构 | `rules/global.md` | 第三章"系统架构" |
| 技术栈/开发环境 | `rules/global.md` | 第二章"技术栈" |
| 编码规范 | `rules/global.md` | 第四章"编码规范" |
| 功能拆分（全局大纲） | `context/progress.md` | 整个文件 |
| 当前任务实现思路 | `context/active.md` | "实现思路"段 |
| 当前任务边界条件 | `context/active.md` | "边界条件"段 |
| 完成后的实现思路归档 | `logs/archive.md` | 按日期追加 |
| Bug 根因分析 | `logs/archive.md` | 按日期追加 |
| 技术选型记录 | `logs/archive.md` | 按日期追加 |
| 今天改了什么 | `logs/changelog.md` | 按日期追加 |
| 某模块设计约定 | `rules/xxx.md` | "架构约定"段 |
| 某模块踩坑记录 | `rules/xxx.md` | "踩坑记录"段 |

---

## 三层权限模型

| 层级 | 目录 | AI 权限 | 维护者 | 更新方式 |
|------|------|---------|--------|---------|
| 🔒 只读层 | `rules/` | 只读 | 开发者手动 | 修改/追加 |
| 📝 读写层 | `context/` | 可覆写 | AI 自动 | 覆写(active) / 局部更新(progress) |
| 📎 追加层 | `logs/` | 仅追加 | AI 自动 | 顶部追加，不改旧内容 |

---

## 已有项目接入（冷启动）

### 第 1 步：复制 .ai 模板到项目根目录

### 第 2 步：让 AI 扫描生成初稿
> "扫描项目目录结构和核心代码，帮我填充 `.ai/rules/global.md`。"

### 第 3 步：审核修改
AI 生成的初稿不一定准确，你需要亲自审核 `rules/global.md`。

### 第 4 步：梳理功能清单
> "根据代码现状，在 `.ai/context/progress.md` 中生成功能清单，已完成的打钩。"

### 第 5 步：迁移旧文档

| 旧文档内容 | 迁移到 |
|----------|--------|
| 需求/架构设计 | `rules/global.md` |
| 模块规范 | `rules/xxx.md` |
| 功能清单/TODO | `context/progress.md` |
| Bug 记录/设计决策 | `logs/archive.md` |

迁移完成后归档或删除旧散装文档。

---

## 双工具协同（Antigravity + Codex CLI）

| 任务类型 | 用 Antigravity | 用 Codex CLI |
|---------|---------------|-------------|
| 新功能规划 | ✅ | |
| 架构设计/重构 | ✅ | |
| 复杂 Bug 分析 | ✅ | |
| 多文件联动修改 | ✅ | |
| 单文件快速修复 | | ✅ |
| 编译报错修复 | | ✅ |
| 跑测试/构建 | | ✅ |

**核心原则：** 共享同一套 `.ai/`，无论谁完成工作都要更新日志。

---

## FAQ

### Q: archive.md 太大怎么办？
每季度归档：旧内容移到 `logs/archive-2025.md`，主文件重新开始。

### Q: rules 文件变太长？
按模块拆分。如 `rules/ui.md` 太长，拆成 `rules/ui-table.md` 和 `rules/ui-dialog.md`。

### Q: 不确定信息放哪？
问自己：**这条信息半年后还有用吗？**
- 永久有用 → `rules/` 或 `logs/archive.md`
- 只对当前任务有用 → `context/active.md`
- 是流水账 → `logs/changelog.md`

### Q: active.md 覆写前忘了归档怎么办？
系统提示词已约束 AI 必须先归档再覆写。如果 AI 跳过了，提醒它："你忘了先归档 active.md 了，请先执行归档流程。"
