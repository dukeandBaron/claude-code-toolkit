# 三角集成架构 v2.2 — 2026-05-28（审计更新）

```
┌─────────────────────────────────────────────────────┐
│                   SHARED MEMORY HUB                  │
│                  ~/.shared-memory/                    │
│                                                       │
│  MEMORY.md ← 三方共读共写的长期记忆                   │
│  TASK_QUEUE.md ← 统一任务队列（三方发布/领取）        │
│  HANDOVER.md ← 交接区（任务结果传递）                 │
│  ACTIVITY_LOG.md ← 活动日志（谁干了啥）               │
│                                                       │
├──────────┬──────────────┬────────────────────────────┤
│          │              │                             │
│  WorkBuddy  │  Claude Code  │    Hermes Agent           │
│  (桌面GUI)  │  (编码主力)   │   (自治+调度+监控)        │
│          │              │                             │
│  读写: ✅   │  读写: ✅     │   读写: ✅                │
│  Skills:613 │  Skills:613   │   Skills:613              │
│  角色:      │  角色:        │   角色:                   │
│  - 交互入口 │  - 代码实现   │   - 定时任务(cron)        │
│  - 记忆管理 │  - Debug      │   - 论文/新闻监控         │
│  - 任务发布 │  - 重构       │   - 子agent调度           │
│  - 可视化   │  - 专利撰写   │   - 系统巡检              │
│  - Expert   │  - Skill触发  │   - session回溯           │
│    人格系统 │    (CLAUDE.md)│   - 记忆双向同步          │
└──────────┴──────────────┴────────────────────────────┘
```

## 数据流

### 1. MEMORY.md (长期记忆)
- 任何一方发现重要事实 → 写入 ~/.shared-memory/MEMORY.md
- 任何一方启动时 → 读取此文件作为上下文
- Hermes: prefill_messages_file 自动注入 + memory tool 双向同步
- Claude Code: CLAUDE.md 启动指令读取 + 会话结束写 ACTIVITY_LOG
- WorkBuddy: 直接读写

### 2. TASK_QUEUE.md (任务队列)
- 任何工具都可以发布任务，任何工具都可以领取
- 状态：pending → in_progress → done / failed
- 格式：`[状态] 任务标题 | 发布者 | 优先级 | 领取者 | 备注`

### 3. HANDOVER.md (交接)
- 跨工具任务结果传递
- 格式：`[日期] [来源工具] 任务标题 → 结果`

### 4. ACTIVITY_LOG.md (活动日志)
- 每次会话结束时追加一行
- 格式：`[YYYY-MM-DD HH:MM] [工具名] 做了什么`
- 保留最近 100 条

## Skills 共享

### 存储
- **源目录**：`~/.workbuddy/skills/`（613 个，WorkBuddy 维护）
- **Claude Code 副本**：`~/.claude/skills/`（独立副本，2026-05-26 同步）
- **Hermes 副本**：`~/AppData/Local/hermes/skills/`（独立副本，2026-05-28 同步）

### 触发机制
- **Claude Code**：CLAUDE.md 中有关键词→skill 映射表，匹配后读取 SKILL.md 执行
- **Hermes**：SOUL.md 中有关键词→skill 映射表，匹配后读取 SKILL.md 执行
- **WorkBuddy**：原生 skill 系统

### 同步
- 新增 skill 放入 `~/.workbuddy/skills/`，需要手动同步到其他两个目录
- 同步命令：`cp -r ~/.workbuddy/skills/<name> ~/.claude/skills/ && cp -r ~/.workbuddy/skills/<name> ~/AppData/Local/hermes/skills/`

## 记忆同步机制

| 工具 | 读取方式 | 写入方式 | 强制执行 |
|------|----------|----------|----------|
| Claude Code | CLAUDE.md 启动指令 | CLAUDE.md 会话结束指令 | 是（prompt 级） |
| Hermes | prefill_messages_file | SOUL.md 同步规则 | 是（prompt 级） |
| WorkBuddy | 直接读取 | 直接写入 | 是（原生） |

## 当前状态（2026-05-28 审计更新）

| 组件 | 状态 | 备注 |
|------|------|------|
| 共享记忆中心 | ✅ 运行中 | 6 个文件，结构完整 |
| Claude Code skills | ✅ 613 个 | CLAUDE.md 有触发协议 |
| Hermes skills | ✅ 613 个 | SOUL.md 有触发协议 |
| Hermes prefill | ✅ 双向 | prefill + SOUL.md 强制回写 |
| Claude Code hooks | ⚠️ 仅音频 | Stop beep，无文件写入 hook |
| Hermes cron | ✅ 已配置 | 每日9:00共享记忆健康检查 |
| 任务队列 | ✅ 运行中 | 6个任务，5个已完成 |
| 交接区 | ✅ 运行中 | 三角架构v2部署结果已交接 |
| MiMo Token | ⚠️ 5/31 过期 | 6/1 用户续费 |
