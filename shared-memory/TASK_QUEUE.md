# 统一任务队列

> 任何工具都可以发布任务，任何工具都可以领取
> 状态：pending → in_progress → done / failed

## 格式
```
- [状态] 任务标题 | 发布者 | 优先级 | 领取者 | 备注
```

## 当前队列

- [done] 三角集成架构 v2 部署 | Hermes | 高 | Hermes | 共享记忆中心+三方接入+记忆压缩
- [done] Claude Code skills 触发协议 | Hermes | 高 | Hermes | CLAUDE.md 加入关键词→skill 映射表
- [done] Hermes SOUL.md 强制回写规则 | Hermes | 高 | Hermes | 6 条强制同步规则
- [done] Hermes cron 任务 | Hermes | 中 | Hermes | 每日 9:00 共享记忆健康检查
- [done] ARCHITECTURE.md 更新 | Hermes | 中 | Hermes | 修正过期信息，v2.1
- [pending] MiMo Token Plan 续费 | 用户 | 高 | 用户 | 2026-06-01 手动续费

## 已完成

（见上方 [done] 项）
