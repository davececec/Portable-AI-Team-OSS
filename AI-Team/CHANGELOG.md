# 团队变更记录（CHANGELOG）

本文件是 Portable AI Team 升级、改动、新增功能的唯一溯源记录。凡是团队自身（胶囊、`AI-Team/`、桥接、规则、模板、配置、脚本、记忆）的变更，都必须记录在这里；业务项目代码变更不记入。

## 记录规则

- 每次升级/改动/新增功能，在“最新在上”的位置追加一条。
- 每条必含：日期、版本或标记、改动类型（新增/修改/修复/移除/升级）、涉及文件、原因与影响、验证方式。
- 修改了 `LLM配置.json`、`team.json`、角色资料、模板或路由策略时，同步核对引用一致性。
- 版本号变更时同步更新 `AI-Team/team.json` 与 `团队状态.json` 的版本字段。
- ZH 每次完成团队自身变更后，收尾时必须更新本文件，并在对应工单尾部追加：`变更记录：已更新 CHANGELOG`。

## 2026-11-06 v4.2.0（完整历史随队迁移）

- 类型：可迁移性升级
- 内容：
  - **完整历史区**：新增 `AI-Team/history/workspaces/`、`manifest.json` 和说明；升级前快照当前工作区及项目根下 `Portable-AI-TeamV*`、团队归档目录。
  - **保留原始现场**：快照包含旧项目工单、`dist`、`.git`、`.pytest_cache`、`__pycache__` 和本地状态，解决团队换项目后无法查看旧项目历史的问题。
  - **运行层隔离**：历史区只用于追溯，IDE 桥接仍只能指向 `Portable-AI-Team/` 当前实体。
  - **升级器增强**：合并既有历史清单，限制快照路径越界，在 `upgrade_history` 记录历史清单和快照数量；失败时继续恢复旧目录和桥接。
  - **doctor 增强**：校验历史 README、manifest、快照路径存在性及是否越界。
  - **版本文件改名**：`VERSION_V4.1.json` 更新为 `VERSION_V4.2.json`；稳定入口 `VERSION.json` 保持不变。
  - **发布边界**：完整历史随整个团队文件夹迁移，但跨 IDE 分发包 ZIP、母版同步继续排除私有历史、Git、构建和缓存。
- 涉及文件：`VERSION.json`、`VERSION_V4.2.json`、`AI-Team/team.json`、`AI-Team/team.py`、`AI-Team/upgrade_carry.ps1`、`AI-Team/capsule.py`、`AI-Team/check_compatibility.py`、`AI-Team/sync_master.ps1`、`AI-Team/history/**`、`AI-Team/versions/**`、`README.md`、`START-HERE.md`、`PROGRESS.md`、`tests/**`。
- 原因与影响：V4.1 只继承运行状态和通用记忆，未携带旧 示例项目 工单、构建与 Git 现场。V4.2 将团队从“代码胶囊”提升为“可追溯的完整工作档案”。
- 验证：部署副本 37/37 测试通过，`doctor` healthy，兼容性构建通过；实际迁移生成 3 个快照，V3.0 原位与快照的 658 文件、17,950,729 字节和聚合 SHA-256 完全一致。详见 `AI-Team/versions/V4.2.md` 与 V4.2 工单。

## 2026-11-06 v4.1.0（稳定运行路径）

- 类型：架构修正 / 升级
- 内容：
  - **固定当前实体路径**：业务项目中的团队实体固定为 `Portable-AI-Team/`，不再使用 `Portable-AI-TeamV<版本>/dist/Portable-AI-Team/` 作为运行时目标。
  - **版本声明与路径分离**：新增 `VERSION.json` 稳定机器入口和 `VERSION_V4.1.json` 版本展示副本；`doctor` 校验两者与 `AI-Team/team.json`、`团队状态.json`、`AI-Team/team.py` 一致。
  - **升级器重写**：`upgrade_carry.ps1` 先在暂存目录组装新版并继承团队状态、安装清单、记忆状态、LLM 配置、凭据和记忆账本，再归档当前实体并替换固定路径；失败时恢复旧目录和桥接。
  - **归档策略**：旧式当前目录整目录移入 `.archive-*`；当前项目 V4.0 归档，V3.0 原位保留。
  - **doctor 收紧**：受管桥接中任何 `Portable-AI-TeamV*` 运行时路径都判失败；启用项目的胶囊实体必须等于 `<项目根>/Portable-AI-Team`。
- 原因与影响：V4.0 虽然能通过标记找到团队，但版本父目录仍在桥接路径中，升级仍会改变所有 IDE 入口。V4.1 将“内容升级”和“入口位置”彻底解耦。
- 验证：专项测试覆盖固定路径启用、V4.0→V4.1 实际迁移、V3 保留、V4 归档、本地私有状态继承、版本不一致拒绝和 doctor 路径检查；项目与母版全量测试结果见对应工单。

## 2026-11-06 v4.0.0（自愈式升级框架）

- 类型：升级
- 内容：
  - **项目根显式化**：`capsule.py enable` 新增 `--project <项目根>`；解析顺序为显式参数 → 向上查找 `.portable-ai-team.json` → `.git` → `AGENTS.md` + `.agents/.codex` → 传统直接子目录布局 → 报错。嵌套 `dist` 布局禁止回退猜测。启用成功后在项目根写入 `.portable-ai-team.json`。
  - **模板占位符化**：`AI-Team/bridges/**` 与 `AI-Team/adapters/**` 中 11 个文件的胶囊路径改为 `{{CAPSULE_PATH}}`，`bridge_source()` / `claude_block()` 使用胶囊相对项目根的真实路径渲染。
  - **enable 幂等与自愈**：AGENTS.md / CLAUDE.md 只替换标记区块，区块外项目自定义内容保留；安装清单内的桥接文件原地覆盖，不再生成 `portable-ai-team-2.*` 副本；重复 enable 返回 `repaired` 而不是 `already_enabled`。
  - **版本档案**：新增 `AI-Team/versions/manifest.json`、`versions/V3.1.1.md`、`versions/V4.0.md`；项目 `团队状态.json` 新增 `upgrade_history`。
  - **doctor 体检**：新增项目根、版本一致、版本目录、模型路由、桥接路径解析、当前版本路径、重复锚点、记忆容量检查；缺少 `LLM配置.json` 改为正常提示（宿主内置模式）。
  - **模型档位路由**：新增 `AI-Team/config/model-tiers.json`，角色绑定 `fast / standard / high-risk / vision` 档位；`policies/model-routing.md` 更新为档位制，V3.x 模型表降级为历史参考。
  - **升级脚本重写**：`upgrade_carry.ps1` 改为"保留旧版目录 + 放入新版胶囊 + 按缺省继承旧安装清单、团队状态、记忆修订和本地私有配置 + 调用新版 enable 重新渲染 + 写升级历史 + 失败回滚"，不再依赖逐文件字符串替换。
  - 版本号统一为 `4.0.0`：`AI-Team/team.json`、`AI-Team/team.py`、`README.md`、`START-HERE.md`、`PROGRESS.md`、`团队状态.json`。
- 涉及文件：`AI-Team/capsule.py`、`AI-Team/team.py`、`AI-Team/team.json`、`AI-Team/upgrade_carry.ps1`、`AI-Team/config/model-tiers.json`、`AI-Team/versions/*`、`AI-Team/policies/model-routing.md`、`AI-Team/bridges/**`、`AI-Team/adapters/**`、`AI-Team/CHANGELOG.md`、`README.md`、`START-HERE.md`、`PROGRESS.md`、`tests/*`。
- 原因与影响：把"路径、版本、模型 ID"三类易变项收敛为单一事实源；升级不再依赖手工改路径，重新 enable 即可修复大多数桥接漂移。
- 验证：2026-11-06 在 `<验证项目路径>` 实跑 V3.1.1 → V4.0.0；`doctor` healthy，项目根/版本/版本目录/模型档位/桥接路径/记忆容量通过，3 个模型连通正常；10 个桥接入口均为 V4.0，旧版本路径和 `{{CAPSULE_PATH}}` 残留均为 0；AGENTS 区块外项目内容保留；`upgrade_history` 记录完整。母版全量测试 `32 tests` 通过（`1 skipped`，为母版无项目 `团队状态.json` 的既有条件跳过）；项目 V4 胶囊全量测试 `32 tests` 通过（无跳过）。

## 2026-11-06 v3.1.1（路径锚定 + 升级脚本 + 跨版本兼容）

- 类型：修复 / 新增
- 内容：
  - **修复**：`capsule.py` 的 `agents_block()` 不再写死 `Portable-AI-Team/`，改为读取 `CAPSULE_ROOT.name` 作为锚点动态生成；`policies/ui-routing.md` 的引用路径同步锚定。解决"胶囊放在 `dist` 等子目录下时，AGENTS.md 与全部桥接文件指向不存在路径"的断链问题（本次审查在示例验证项目项目定位到根因）。
  - **新增**：母版根目录 `胶囊根.txt` —— 团队路径锚点文件，内容恒为 `Portable-AI-Team`；母版是锚点唯一权威源，新项目建团一律从母版整份复制后启用，锚点不允许每个项目自选。
  - **新增**：`AI-Team/upgrade_carry.ps1` —— 版本升级脚本。用法：在业务项目根目录执行 `powershell -File <胶囊>\AI-Team\upgrade_carry.ps1 -NewVersion V4.0 [-OldVersion V3.0] [-DryRun]`。脚本只做三件事：①把旧版本父目录（如 `Portable-AI-TeamV3.0`）备份到 `.backup-<旧>-<时间戳>`；②把新版本父目录（如 `Portable-AI-TeamV4.0`）复制进项目根；③对 10 个桥接文件做版本父目录字符串替换。锚点 `Portable-AI-Team/AI-Team/` 子树完全不动。
  - **升级约定**：版本父目录（`Portable-AI-TeamV3.0` / `V4.0` / …）是易变项，**禁止**出现在团队契约性字符串里；所有桥接文件只引用"版本父目录 + 锚点子路径"的组合，升级时只替换版本父目录那一层。
  - **doctor 降噪**：`capsule.py doctor` 不再把"缺 LLM配置.json"当错误（Codex 环境本就回退内置子代理，`LLM配置.json` 按脱敏规则不进胶囊），改为提示"未配置外部 LLM，使用宿主内置"。
  - **跨 IDE 桥接**：本项目 `.codex/agents/*.toml`、`.agents/agents/*/agent.md`、`.trae/rules`、`.workbuddy/rules`、`AGENTS.md` 团队区块全部重写为真实路径；AgentA.md 中 `\python ...\` 等反斜杠转义统一改为反引号。
- 涉及文件：`AI-Team/capsule.py`、`AI-Team/CHANGELOG.md`、`AI-Team/team.json`、`AI-Team/upgrade_carry.ps1`（新增）、`胶囊根.txt`（新增）、`AI-Team/agents/AgentA.md`、`AI-Team/bridges/codex/agent-{b,c,d}.toml`、`AI-Team/bridges/trae/portable-ai-team.md`、`AI-Team/bridges/antigravity/portable-ai-team.md`、`AI-Team/bridges/antigravity/agent-{b,c,d}.md`、`AI-Team/bridges/workbuddy/portable-ai-team.md`、`AI-Team/bridges/claude/claude.md`、`AI-Team/memory/index.md`（双路径规则修正）。
- 原因与影响：解决"版本目录名漂移"与"路径写死"叠加导致的跨版本断链；以后升级只需跑一条 `upgrade_carry.ps1`，不需要逐文件改路径。锚点文件让"团队主体目录名"从口头约定变成可校验的契约。
- 验证：本项目 `<验证项目路径>` 内 10 个桥接文件路径全部可解析；`python -m py_compile capsule.py` 通过；`upgrade_carry.ps1 -DryRun` 在临时目录验证幂等性（待补）。
## 2026-11-02 v3.1.0
  - 保留 GITHUB 侧文档 `AI-Team/policies/multi-session-dispatch.md`（多会话并行调度手册）与 `Python路径.txt.example`，v3.1.0 同步合入。
 五平台适配 + 模型接入指南 + doctor 自检 + 脱敏

- 类型：新增 / 修改
- 内容：
  - 新增 **Claude Code** 桥接：`capsule.py enable` 在项目中已存在 `CLAUDE.md` 时，向其中追加带标记的团队区块（`claude_block` / `append_marked_block`），可逆，`carry` 时整块移除；不存在则不创建。标注"未官方验证"。
  - 新增 **WorkBuddy** 桥接：`AI-Team/bridges/workbuddy/portable-ai-team.md` 写入 `.workbuddy/rules/`，按 A->C->B->D->C 顺序模拟角色。官方无 rules 目录规范，采用保守方案，标注"未官方验证"。
  - `capsule.py` 的 `BRIDGES` 注册 9 个目标；`alternative_target()` 对 `workbuddy-rule` 与 trae/antigravity 同等处理；新增 `CLAUDE_BLOCK` 标记与 `claude_block()` 生成逻辑。
  - `check_compatibility.py` 校验 `.workbuddy/rules/portable-ai-team.md`（顺序降级 + 独立验收）与 `CLAUDE.md`（若存在），`required` 清单加入五平台文档与桥接；`EXCLUDED_PARTS` 由 `memory-backup-20261010` 更新为 `seed`。
  - 平台矩阵 `compatibility-matrix.md` 更新为五平台；新增 `ide-guides/claude-code.md` 与 `ide-guides/workbuddy.md`。
  - `LLM配置.example.json` 改为厂商中立：占位符 + `_说明` 字段，无真实密钥、无内部网关。
  - 新增 `AI-Team/references/llm-接入指南.md`：复制示例 -> 填 `base_url`/`api_key`/`models` -> 跑 `capsule.py doctor` 的 30 秒上手流程。
  - 新增 `capsule.py doctor` 命令：离线结构校验（`validate_llm_config`）+ 每模型最小 ping（`probe_one`）+ Python/团队版本/LLM 配置/桥接完整性检查（`doctor_capsule`），逐条打印结果。
  - 脱敏：`references/enterprise-llm-gateway-api.md` 重命名为 `references/enterprise-llm-gateway-api.md`；CHANGELOG 中内部网关地址替换为 `internal-llm-gateway`；`memory-backup-20261010` 迁入 `AI-Team/seed/memory-20261010`（IP 替换为 `<内网IP>`，删除 `credentials.md` 与 `记忆账本.json`）。
  - `.gitignore` 追加：`AI-Team/seed/memory-*/credentials.md`、`AI-Team/seed/memory-*/记忆账本.json`、`AI-Team/ui-design-kit/示例项目-*`、`AI-Team/ui-design-kit/design-system-demo-*`、`AI-Team/evidence/`。
  - README 与 START-HERE 全面升级为 v3.1.0 五平台版：新增 LLM 接入步骤、平台说明、种子记忆说明。
  - 版本号统一为 `3.1.0`：`AI-Team/team.json`、`AI-Team/team.py`、`团队状态.json`。
- 涉及文件：`AI-Team/capsule.py`、`AI-Team/check_compatibility.py`、`AI-Team/team.py`、`AI-Team/team.json`、`AI-Team/ide-guides/compatibility-matrix.md`、`AI-Team/bridges/claude/claude.md`（新增）、`AI-Team/bridges/workbuddy/portable-ai-team.md`（新增）、`AI-Team/ide-guides/claude-code.md`（新增）、`AI-Team/ide-guides/workbuddy.md`（新增）、`AI-Team/references/llm-接入指南.md`（新增）、`AI-Team/seed/memory-20261010/`（迁入）、`AI-Team/CHANGELOG.md`、`LLM配置.example.json`、`README.md`、`START-HERE.md`、`PROGRESS.md`、`.gitignore`、`tests/test_release_metadata.py`、`tests/test_agent_d.py`
- 影响：跨 IDE 从 3 平台扩展到 5 平台；模型接入从"看源码"变成"看指南 + 跑 doctor"；分发包 ZIP 不再携带经验备份，改为 seed 目录（不进入 ZIP）。
- 验证：`python -m unittest discover -s tests -v` 26 项全过；`python AI-Team/check_compatibility.py --build` 通过；冒烟测试（临时项目 enable -> validate -> carry，含 CLAUDE.md 与不含 CLAUDE.md 两种情况）全部通过。

## 2026-11-02 智能团队宣传 PPT v3.0

- 类型：新增（宣传物料升级）
- 内容：团队能力宣传 PPT 从 v2 13 页升级为 v3 18 页（中英双版同步）。新增 5 个页面：S5 独立验收（第一设计原则独立成页）、S6 经验库复利（复利曲线 + 四类可积累资产）、S11 AgentC 视觉验收（截图独立走视觉模型、只回结论）、S15 成本对比（示例车间 Phase 5 前端页面真实定价估算，单 AI 约 3~5 元/页 vs 团队约 0.30 元/页、闲时约 0.10 元/页，降幅约 90%）、S16 失败案例（ECharts 周期切换静默 bug：发现 → 根因 → 3 行修复 → 验证，源自 2026-10-16 示例车间 Phase 6 工单）。封面 tagline 改为「一支团队，不是一个聊天机器人 / A Team, Not a Chatbot」，副标题拆三行短句；S3 增加 ZH 角色脚注（ZH = the orchestrator role, named after its creator）；S18 上手三步改为 30 秒终端实录（Copy-Item / capsule.py enable / 一句话下单）；S7 八大能力与 S12 Token 节省页加交叉引用（p.5 / p.11）；S17 长期价值新增「开源起步：方法论 + adapter 框架，用市场检验」。
- 涉及文件：`docs/ppt/build_v3/build_ppt_v3.py`（中文版）、`docs/ppt/build_v3/build_ppt_v3_en.py`（英文版）、`docs/ppt/output/Portable-AI-Team-智能团队能力-v3.pptx`、`docs/ppt/output/Portable-AI-Team-Capabilities-v3-EN.pptx`。
- 原因与影响：对外讲解从「机制罗列」升级为「卖点前置 + 真实数字 + 诚实故事」，英文版可直接面向海外受众。
- 验证：两版各 18 页渲染走查（render / render_en 逐页 PNG），S5/S6/S11/S15/S16/S17/S18 无溢出无重叠；python-pptx 构建无报错。

## 2026-10-13 UI kit 入位 + 数据配色系统（第 8 章）

- 类型：新增 / 修改
- 内容：①三风格 UI 设计标准包入 `AI-Team/ui-design-kit/`（规范 + design-tokens.css + shopeers-ui.css + shopeers-echarts-theme.js + echarts.min.js + 3 风格 demo + AGENTS/README），修复 `memory/index.md` 失效指向 `../UI/UI-DESIGN-STANDARD.md`，注明优先级（项目自有标准 > kit 默认，未指定默认 Light SaaS）。②`UI-DESIGN-STANDARD.md` 新增「第 8 章 数据配色系统」（同实体同色、语义色+类别色、矩阵 √比例色阶、log10 轴、负值红字 #F87171、占比空态、趋势语义双色、参考实现），原第 8 章交付检查清单顺延为第 9 章并新增配色检查项。③`design-tokens.css` 新增 `--kind-1..9` / `--ws-1..11` / `--data-neg` token；README 新增第 4 条使用方式。
- 涉及文件：`AI-Team/ui-design-kit/*`、`AI-Team/memory/index.md`（示例项目 业务侧 palette.js 不入本文件，见 示例项目 项目时间线）。
- 原因与影响：UI 规范与配色体系可供后续项目直接复用；新页面派单 C 时 spec 必读 kit 对应风格章。
- 验证：kit 10 文件齐、index.md 指向有效；示例项目 浏览器实测（排名多色、9 色介质图、√色阶矩阵、log10 轴）console 零报错，见 示例项目 时间线 2026-10-13。

## 2026-10-12 桥接清单字节对齐

- 类型：修复
- 内容：`state/installation.json` 中签约给项目 AGENTS.md 的团队区块原以 LF 存储，磁盘文件为 CRLF，导致 `capsule.py validate` 持续报“AGENTS.md 团队区块已修改”、`carry` 无法移除区块完成复位。按磁盘原始字节重建 stored block（前导/结尾换行一并对齐）。
- 涉及文件：`state/installation.json`；项目 `AGENTS.md` 未改动。
- 验证：`capsule.py validate` 返回“团队桥接校验通过”。

## 2026-10-12 公司大模型网关参考文档

- 类型：新增文档
- 内容：新增 `AI-Team/references/enterprise-llm-gateway-api.md`，整理 `internal-llm-gateway` 三接口速查（Chat 文本生成 / Chat 图像理解含思考模式 / Completions 纯文本补全），含请求字段、响应解析、LangChain/LlamaIndex/HTTP 示例与实测核对结论。
- 涉及文件：`AI-Team/references/enterprise-llm-gateway-api.md`（新增）；`AI-Team/memory/index.md`、`AI-Team/templates/task-standard.md`、`AI-Team/templates/task-micro.md`（加入引用入口，直连网关任务先查本参考，避免重复探测）。
- 影响：团队编写直连网关的脚本/业务代码时可直接复用已验证的调用格式，减少测试消耗与试错。
- 验证：文档内端到端实测 `default/qwen3-vl-30b-a3b-instruct` 图像理解、`default/minicpm-v-2-6` 图像可用；`default/glm-4v-9b` 网关不存在（403），保留为参考资料说明。

## 2026-10-12 子代理通道降级规则 + 视觉接口配方

- 类型：修复 / 新增规则
- 背景：Codex 内置子代理在当前环境（Codex++ 中继 → `internal-llm-gateway`，仅支持 Chat Completions）派发稳定报 `unsupported_encrypted_agent_content`；此前团队会盲目重试 3 轮后卡死。
- 涉及文件：
  - `AI-Team/policies/model-routing.md`：新增“内置子代理通道可用性告警”“故障与降级”章节；首次派单只探针 1 次，命中该协议错误即判定环境限制并顺序降级，禁止盲目重试；补充第 5 条“降级标注”规则。
  - `AI-Team/agents/AgentA.md`：多模型并行派单节新增探针与降级判定；无子智能体能力节新增降级任务标注要求。
  - `AI-Team/adapters/codex/AGENTS.md`：Codex 桥接同步探针、降级与禁止重试规则。
  - `AI-Team/capsule.py`：启用器生成的新项目 AGENTS.md 区块加入探针+降级句，新部署即生效。
  - `README.md` / `START-HERE.md`：新增“已知平台限制与排障”说明。
  - `AI-Team/memory/effective-solutions.md`：新增已验证的视觉接口配方（`/chat/completions` 图片理解格式）。
- 影响：子代理不可用时团队不再卡死，自动按角色顺序模拟执行（对话+工单各标一次，收尾 A 独立验收再标一次）；视觉理解可走外部 Chat Completions 通道。
- 验证：`py_compile` 通过；`llm_dispatch.py --test` 全模型可用；视觉接口实测 `default/qwen3-vl-30b-a3b-instruct`、`default/minicpm-v-2-6` 成功，`default/glm-4v-9b` 不存在（403）。

## 2026-10-10 v3.0.0 基线

- 类型：版本基线
- 内容：团队胶囊 v3.0.0 首发。AgentB 与 AgentD 并行分担；`LLM配置.json` 外部 API 多模型调度（`llm_dispatch.py` 探测/单发/并行/失败降级）；`capsule.py` enable/validate/carry/merge；Codex、Google Antigravity、TraeCode 三端桥接与兼容矩阵；记忆合并兼容 v2.3+。
- 详细说明见 `README.md` 的“V3.0 变更”“外部模型与并行派单”章节。
