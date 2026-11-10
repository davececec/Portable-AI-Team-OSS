# Memory Index

Read this index first, then load 1-3 relevant files per task.
Never load all memory files by default.

| Category | File | When to read |
| --- | --- | --- |
| User preferences | `user-preferences.md` | Communication, output, or interaction preferences |
| Tech stack | `tech-stack.md` | Technology selection, build, compatibility |
| Completion criteria | `completion-criteria.md` | Defining acceptance or delivery boundaries |
| Feedback patterns | `feedback-patterns.md` | Handling recurring user feedback |
| Defect patterns | `defect-patterns.md` | Debugging or regression risk |
| Effective solutions | `effective-solutions.md` | Reusable implementation or troubleshooting |
| Technical decisions | `technical-decisions.md` | Architecture, dependencies, tradeoffs |
| Project history | `project-history.md` | Modifying existing projects or restoring context |

Each entry max 300 chars; each file max 40 entries and 8,000 chars.
When either limit is reached, create a dated attachment under
`attachments/`, keep the original memory file unchanged, and add only a
lightweight pointer to the main index/file. Never delete or rewrite old
memory merely to fit a limit. If duplication or meaning is uncertain, keep
the original text and mark it for later review. Only record new, stable
lessons; do not invoke a model just to update memory.

## Attachments

| Date | File | Scope |
| --- | --- | --- |
| 2026-11-02 | `attachments/2026-11-02-示例项目-阶段记忆.md` | 示例项目 2026-10-22 to 2026-11-02 phase facts, current handoff, evidence |
| 2026-11-02 | `attachments/2026-10-22-2026-11-02-技术经验.md` | Stable data, AI, deployment, and acceptance lessons from the same period |
| 2026-11-03 | `attachments/2026-11-03-示例项目-进度与验证记忆.md` | 示例项目 2026-11-03 energy, hierarchy, production, delivery, server sync, and baseline facts |
| 2026-11-05 | `attachments/2026-11-05-示例设备监控系统-阶段记忆.md` | 示例设备监控系统（新建）：agent 主动上报架构、MAC 设备键、端口 8031、exe 交付形态、IP 检测、远程部署备忘 |
| 2026-11-05 | `attachments/2026-11-05-团队母版机制.md` | 团队母版机制：中央母版、一键回写流程、排除规则与首日实测 |
| 2026-11-06 | `attachments/2026-11-06-团队V4.2完整历史携带.md` | V4.2 完整工作区历史、旧项目工单与 Git/构建现场随队迁移决策 |
| 2026-11-07 | `attachments/2026-11-07-示例设备监控-阶段记忆.md` | 示例设备监控系统：8030/8031/8032 三入口、车间分配、温度推算、Style 03 UI 重设计与发布经验 |

## Project documents

| Date | File | Scope |
| --- | --- | --- |
| 2026-11-06 | `project-docs/environment-monitor/2026-11-06-data-mapping.md` | 示例验证项目数据源、设备/指标、数据库表、报警与通知链路映射 |
| 2026-11-06 | `project-docs/environment-monitor/tasks/` | 示例验证项目工单、变更、验证和验收记录，按项目目录保存 |

Attachment rule (2026-11-02): when a main memory file exceeds the suggested
limit, preserve its complete original content and add the new material to a
dated attachment. The main memory file should only gain a pointer. Do not
compress away valuable history, and do not create a rewritten summary that
changes the meaning of the original entries.

When the project is complete or the team is about to be carried away,
AgentA compresses the project summary into `project-history.md`
and updates other categories as needed. Only carry stable, reusable
conclusions. Never record business source code, secrets, raw logs,
build artifacts, or project dependencies.

**Credential lookup rule (updated 2026-11-06):** When the user says "记下来/按规定放" about any account+password (database / Windows / LLM / web login), the ONLY correct target is `Portable-AI-Team/AI-Team/memory/credentials.md` (authoritative) + `团队经验速查手册.md` §11 (mirror). Do NOT write to `.env` (runtime config only), tickets, README, or chat. The current team entity always lives at the project-root path `Portable-AI-Team/`; version directories are historical archives, not runtime lookup targets.
**Credential active-capture rule (2026-11-05, user standing order):** ZH must proactively record any account+password that appears during a session (chat, config, command, or test output) into `credentials.md` (+ 速查手册 §11 mirror) without waiting for the user to remind. Plaintext still lives only in those two files; never spread it into tickets, README, chat body, or public repos.
**Important:** Never commit `credentials.md`, API keys, or any plaintext
passwords to version control. Sensitive credentials must stay in
`LLM配置.json` (git-ignored) and be rotated immediately if exposed.

