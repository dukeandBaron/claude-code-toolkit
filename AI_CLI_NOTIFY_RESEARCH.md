# AI CLI Complete Notify 调研报告

> 项目: ZekerTop/ai-cli-complete-notify
> Stars: 313
> 语言: JavaScript
> 许可: ISC

## 核心功能

### 1. 多通道通知
- **Webhook**: 飞书、钉钉、企微（自动检测平台）
- **Telegram Bot**: 直接发送消息
- **Email (SMTP)**: 邮件通知
- **桌面通知**: Windows 气泡/ macOS/Linux 通知
- **声音/TTS**: 语音提醒
- **智能手环/手表**: 通过现有通知渠道

### 2. 智能去抖（Debouncing）
```
有工具调用: 60秒静默后通知
无工具调用: 15秒静默后通知
```

**设计思路**: Claude Code 经常将一个请求拆分成子任务，为避免垃圾通知，只在整个 turn 完成后才通知。

### 3. 耗时阈值
```javascript
// 只有任务超过设定时长才通知
shouldNotifyByDuration({ minDurationMinutes, durationMs, force })
```

**设计思路**: 短任务（<1分钟）不需要通知，避免频繁打断。

### 4. Hooks vs Watch 两种模式

**Hooks 模式（推荐）**:
- Claude Code: 使用原生 `Stop` hook 事件
- Gemini CLI: 使用原生 `AfterAgent` hook 事件
- OpenCode: 使用全局插件，监听 `session.idle` / `session.error`

**Watch 模式（通用后备）**:
- 通过日志文件监控
- 依赖静默期推断任务完成
- 适用于 Codex 或未配置 hooks 的情况

### 5. AI 摘要（可选）
```javascript
// 生成任务摘要
summarizeTask({ config, taskInfo, contentText, summaryContext })
```

**设计思路**: 长任务生成简短摘要，超时则使用原始任务信息。

### 6. 配置分离
```
运行时配置: settings.json（通道开关、阈值）
敏感信息: .env（API keys、tokens）
```

## 架构设计

### 核心模块
```
src/
├── engine.js          # 核心通知引擎
├── hooks.js           # Hooks 集成（Claude/Gemini/OpenCode）
├── hook-reminder.js   # Hook 提醒逻辑
├── watch.js           # 日志监控
├── config.js          # 配置管理
├── state.js           # 状态管理（去重）
├── summary.js         # AI 摘要
├── format.js          # 格式化
├── notifiers/         # 通知渠道
│   ├── webhook.js     # 飞书/钉钉/企微
│   ├── telegram.js    # Telegram Bot
│   ├── email.js       # SMTP 邮件
│   ├── desktop.js     # 桌面通知
│   └── sound.js       # 声音/TTS
└── watch-log.js       # 日志监控
```

### 关键设计模式

#### 1. 通知去重
```javascript
const NOTIFICATION_DEDUPE_MS = 2 * 60 * 1000; // 2分钟内不重复通知

function checkAndRememberNotification({ source, cwd, text, dedupeMs }) {
  // 检查是否在去重窗口内
  // 如果是，跳过通知
  // 否则，记录并发送通知
}
```

#### 2. 通道开关
```javascript
function isChannelEnabled(config, channelName, sourceName) {
  const channelGlobal = config.channels[channelName]?.enabled;
  const channelPerSource = config.sources[sourceName]?.channels?.[channelName];
  return channelGlobal && channelPerSource;
}
```

#### 3. 来源独立配置
```json
{
  "sources": {
    "claude": { "enabled": true, "minDurationMinutes": 1 },
    "codex": { "enabled": true, "minDurationMinutes": 2 },
    "opencode": { "enabled": false },
    "gemini": { "enabled": true, "minDurationMinutes": 1 }
  }
}
```

## 可借鉴的设计

### 1. 智能去抖机制
**问题**: Claude Code 经常将一个请求拆分成子任务，导致多次通知。

**解决方案**: 
- 监控静默期（无输出的时间）
- 有工具调用时等待更长（60秒）
- 无工具调用时等待更短（15秒）

**应用到我们的 Toolkit**:
```python
class NotificationDebouncer:
    def __init__(self):
        self.last_activity = {}
        self.quiet_threshold = {
            "with_tools": 60,  # 有工具调用
            "without_tools": 15  # 无工具调用
        }
    
    def should_notify(self, session_id, has_tools=False):
        """检查是否应该发送通知"""
        threshold = self.quiet_threshold["with_tools" if has_tools else "without_tools"]
        last = self.last_activity.get(session_id, 0)
        return (time.time() - last) >= threshold
```

### 2. 耗时阈值
**问题**: 短任务不需要通知，避免频繁打断。

**解决方案**: 
```python
def should_notify_by_duration(min_duration_minutes, duration_ms, force=False):
    """只有任务超过设定时长才通知"""
    threshold_ms = min_duration_minutes * 60 * 1000
    if force:
        return True
    if duration_ms < threshold_ms:
        return False
    return True
```

### 3. 多通道通知
**问题**: 不同用户偏好不同的通知方式。

**解决方案**: 支持多种通知渠道，用户可独立开关。

**应用到我们的 Toolkit**:
```python
class NotificationManager:
    def __init__(self):
        self.channels = {
            "webhook": WebhookNotifier(),
            "telegram": TelegramNotifier(),
            "email": EmailNotifier(),
            "desktop": DesktopNotifier(),
            "sound": SoundNotifier()
        }
    
    def notify(self, message, channels=None):
        """发送通知到指定渠道"""
        channels = channels or self.get_enabled_channels()
        for channel in channels:
            if channel in self.channels:
                self.channels[channel].send(message)
```

### 4. 配置分离
**问题**: 敏感信息（API keys）不应和运行时配置混在一起。

**解决方案**: 
- 运行时配置: `settings.json`
- 敏感信息: `.env`

**应用到我们的 Toolkit**:
```python
# ~/.shared-memory/.notify_config.json (运行时配置)
{
  "channels": {
    "webhook": { "enabled": true },
    "telegram": { "enabled": false }
  },
  "thresholds": {
    "min_duration_minutes": 1,
    "quiet_seconds": 60
  }
}

# ~/.shared-memory/.notify.env (敏感信息)
WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxx
TELEGRAM_BOT_TOKEN=xxx
TELEGRAM_CHAT_ID=xxx
```

### 5. Hooks 集成
**问题**: 日志监控不够准确，依赖静默期推断。

**解决方案**: 使用 Claude Code 原生 hooks 事件。

**Claude Code Hook 配置**:
```json
{
  "hooks": {
    "Stop": [
      {
        "type": "command",
        "command": "python ~/.shared-memory/notify.py --source claude --from-hook"
      }
    ]
  }
}
```

## 实施建议

### 阶段 1: 基础通知（1-2天）
1. 实现 Webhook 通知（飞书/钉钉/企微）
2. 实现 Telegram Bot 通知
3. 实现耗时阈值

### 阶段 2: 智能去抖（2-3天）
1. 实现静默期检测
2. 实现工具调用感知
3. 实现通知去重

### 阶段 3: Hooks 集成（3-5天）
1. 实现 Claude Code hooks 安装
2. 实现 hook 事件处理
3. 实现 watch 模式作为后备

### 阶段 4: 高级功能（1周）
1. 实现 AI 摘要
2. 实现桌面通知
3. 实现声音/TTS

## 总结

ai-cli-complete-notify 的核心价值在于：

1. **智能去抖**: 避免子任务导致的垃圾通知
2. **多通道**: 支持 6 种通知渠道
3. **Hooks 优先**: 使用原生事件，比日志监控更准确
4. **配置分离**: 敏感信息和运行时配置分开

**我们可以借鉴**:
- 去抖机制（静默期检测）
- 耗时阈值（短任务不通知）
- 多通道支持（Webhook/Telegram/Email）
- 配置分离（.env 存敏感信息）

**注意**: 这个项目是 JavaScript/Node.js，我们需要用 Python 重新实现核心逻辑。
