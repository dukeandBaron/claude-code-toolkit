# 共享长期记忆

> 三方共用：WorkBuddy / Claude Code / Hermes Agent
> 最后更新：2026-05-28 by Hermes（从 OpenClaw/WorkBuddy/Hermes 旧记忆压缩合并）

---

## 用户信息
- 称呼：兄弟
- 身份：计算机专业学生 + 技术团队管理者
- 时区：Asia/Shanghai
- 语言：中文，直接风格
- 学术目标：投稿 CCF-B 级别会议论文
- 研究方向：3DGS、NeRF、Entropy、Dynamics、Repro System、Research OS
- 擅长：系统型专利布局

## 技术栈
- Python（Django/FastAPI）、Node.js（Express/NestJS）、Java（Spring Boot）
- Win10 / RTX 4060 8GB / PyTorch 2.5.1+CUDA12.1 / Python 3.12
- 中国校园网，清华 PyPI 镜像
- 笔记工具：Obsidian（计划中）

## 当前活跃项目

### 1. 2026龙芯杯 MIPS 双发射处理器（个人赛）
- 基于 nontrivial-mips 开发
- 已实现 4 条转发路径（EX→EX, MEM1, MEM2, WB1）
- 待解决：LW 指令测试阻塞
- 项目路径：`D:\BaiduNetdiskDownload\nontrivial-mips-master`

### 2. 3D Gaussian Splatting 论文复现
- 核心命题：densification + opacity collapse 结构相变
- 项目路径：`D:\blender_render\3dgs-repro\`
- conda 环境：torch-gpu
- 已跑通 T&T truck 场景

### 3. WorkBuddy 项目开发
- 集成 DeepSeek V4 和小米 MiMo V2.5 Pro
- MiMo Token Plan 剩余约 7 亿 tokens，2026-05-31 过期
- 三角集成架构 v2 已部署

### 4. 物理传感器数据采集
- YIXI YSC-4209 / YEK-6702

### 5. 论文转专利项目
- 系统型专利布局与专利族构建

## 历史项目（归档）

### Prophet System v2.0.0（2026-03-22）
- M3 竞争性 ODE 求解器：Vampire Matrix + 能量守恒 ✅
- M4 玻尔兹曼注意力分配 ✅
- M5 坍缩预警系统 ✅
- M6 先手信号识别 ✅
- M7 收割信号识别 ✅
- 项目路径：`D:\lianghua_one\v13_final\sword\prophet_system`

### SmartMaster 智能车竞赛物资数据集（2026-03-25~26）
- 15 类工具/电子设备，3053 张图
- 已用 YOLOv8 生成标注，后改用 RKNN 模型
- 数据路径：`D:\SRC\视觉模块完整备份\7、SmartMaster物资数据集`
- ⚠️ RKNN 模型问题：duzhong0731.rknn 15类 vs 代码期望28类，版本不匹配

### 两位数数字识别系统（2026-03-27）
- YOLOv8-nano 检测器 + MobileNetV3-Small 蒸馏
- 教师模型准确率 96.51%，温度 T=4
- 项目路径：`D:\SRC\视觉模块完整备份\number1`

### 电竞共鸣智能场控系统 Demo
- 位置：`C:\Users\living\Desktop\MindFlow_Bond_System`
- FastAPI + Vue 3 + DeepFace + AIGC
- 状态：已完成 Demo

## 工具链（2026-05-28 更新）
- Claude Code v2.1.150 — 编码主力，skill 触发协议已部署
- Hermes Agent v0.14.0 — 自治调度 + 定时任务 + QQ Bot（待启动 gateway）
- WorkBuddy — 桌面交互入口
- 共享记忆中心：`~/.shared-memory/`（6 个文件）
- Skills 共享：`~/.claude/skills/`（613 个，关键词触发）
- 三者共用 mimo-v2.5-pro 后端（小米 Token Plan，5/31 过期，6/1 续费）
- Conda 修复：PYTHONHOME 污染已解决（.bashrc unset）

## 关键决策记录
- 2026-05-26：C 盘主工作区，D 盘项目级硬链接共享（跨盘硬链接不可行）
- 2026-05-26：不买 Opus，用 DeepSeek V4 Pro via Anthropic 兼容接口
- 2026-05-28：三角架构 v2，共享记忆中心 ~/.shared-memory/，Hermes 正式加入

## 偏好
- 输出：编号列表、LaTeX 公式、结构化排版、可执行命令
- 交互：用户定方向，AI 执行细节
- 决策：先调研再决策，先框架再实现
- 成本意识强，合理分配 Token
