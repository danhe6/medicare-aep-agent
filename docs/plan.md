# Medicare AEP Agent — 30天计划

Sep 26, 2026 · @DAN HE

## 目标与范围

**一句话 pitch：** 一个中立、隐私优先的 Medicare 助手。读懂你的 ANOC，算出每个计划的全年真实成本，揪出隐藏陷阱，并给家人一页决策总结。

**提交目标：** Oct 28, 2026 前提交（官方 deadline 是 Oct 30, 2026 1:00 PM ET）。**Track：** Personal AI，同时冲 Best Use of Tavily。

**MVP 范围（只做这些）：**

- 地域只做 **Miami-Dade, FL**
- 输入：ZIP、药单（手输 / 药瓶照片）、医生名字、当前计划 ANOC（PDF）
- 输出：Top 3 计划排名 + 全年成本拆分、红旗警告、电话核实清单、家人版一页总结
- Persistent memory：用户 profile 和历次决策
- 模型分工：Nano Omni 读图和 PDF、Super 120B 做主 agent、Ultra 550B 做陷阱推理；算钱全部用确定性 Python，在 Sandbox 里跑

**明确不做：** 替用户投保、全美 50 州、Medigap 比价、语音、原生 app。

**成功标准：**

- 10 个测试 persona 的年药费和 Plan Finder 相比误差 ≤ 10%
- Demo 从上传到出结果 ≤ 3 分钟
- 访谈 ≥ 3 位照顾老人的家属，拿到可引用的原话

**时间预算：** 工作日晚上约 2h，周末每天约 6h，合计约 20h/周。

## Agent 考虑范围

Agent 只处理老人看得到、需要做选择的那一层。计划和 CMS 之间怎么结算（HCC / RAF risk adjustment、star rating 计算、bid、MLR）不在范围内。健康状况只用用户自述的信息，不推断、不诊断。

| 维度 | 内容 | MVP |
| --- | --- | --- |
| 药费 | tier、deductible、$2,400 封顶、药房类型、胰岛素 $35、PA / step therapy / 数量限制 | 核心 |
| 医疗费 | 保费、MOOP、PCP / 专科 / 住院 / SNF copay、HMO referral | 核心 |
| 健康状况 → 使用场景 | 用户自述的慢病决定用低 / 中 / 高哪种使用场景来算成本 | 核心 |
| SNP 资格 | C-SNP（特定慢病）、D-SNP（Medicare + Medicaid 双重资格） | 做，归入红旗规则 |
| 补贴 | Extra Help / LIS、Medicaid、Prescription Payment Plan | 做，归入红旗规则 |
| 网络 | 医生、医院、药房 | 显示置信度 + 电话核实 |
| 时间规则 | AEP、MA OEP、SEP、Medigap 回头路 | 做，归入红旗规则 |
| 质量 | Star ratings、计划退出新闻 | 做（Tavily） |
| Supplemental benefits | 牙科、视力、OTC 卡、交通 | 只展示，不计入成本 |
| 复杂身份 | ESRD、VA / TRICARE、雇主退休医保、I-SNP | 识别后转介 SHIP 咨询 |

结果页要有一个“覆盖地图”，分三类告诉用户：已经检查了什么、需要打电话确认什么、什么情况建议找 SHIP 咨询员。

**待确认：** HRDD / HRDM 是什么意思？如果它影响病人自己的费用或选择，就加进上表。

## Week 0（9/26–9/27）：Setup + 最大风险 spike

这个周末只回答一个问题：**用 CMS 公开数据算出来的年药费，跟 Plan Finder 对得上吗？**

| Day | 日期 | 任务 | 产出 |
| --- | --- | --- | --- |
| 1 | 周六 9/26 | 领 Token Factory credits（promo code + Builders Program）；拿 Tavily key；fork starter repo；跑通一次 Nemotron Super 调用；查雇佣合同 side project 条款 | API 跑通、repo 建好 |
| 2 | 周日 9/27 | 下载 Formulary PUF（monthly + quarterly pricing）、landscape、PBP；DuckDB 过滤 Miami-Dade；挑 3 种常见药 × 5 个计划手算年药费，对比 Plan Finder；发消息约 3 位家属下周聊 20 分钟 | Spike 结论 + 误差表 |

**Gate 0（周日晚）：** 误差 ≤ 15% → 继续。误差更大 → 成本引擎改为“相对排名 + 费用区间”，不说精确数字。

## Week 1（9/28–10/4）：数据层 + 成本引擎

本周产出一个不含 LLM 的 Python 引擎：输入药单和 ZIP，输出每个计划的全年成本。这是整个项目的地基，也是你 BI 强项最能发挥的一周。

| Day | 日期 | 任务 | 产出 |
| --- | --- | --- | --- |
| 3 | 周一 9/28 | 设计数据模型（plans / formulary / pricing / pharmacy / benefits）；写 ingest 脚本，数据层可按 plan year 替换 | DuckDB schema |
| 4 | 周二 9/29 | 接 RxNorm API：药名 → RxCUI → NDC；处理剂量和通用名 | `drug_lookup` 工具 |
| 5 | 周三 9/30 | Part D 成本算法：deductible → 初始阶段 → $2,400 封顶（按 2027 规则参数化） | `annual_drug_cost()` |
| 6 | 周四 10/1 | MA 医疗成本：保费 + MOOP + 几种就医场景（低 / 中 / 高使用） | `annual_total_cost()` |
| 7 | 周五 10/2 | 10 个测试 persona（药单 + ZIP）写成 fixture；跑第一版对比 | Eval 数据集 v0 |
| 8 | 周六 10/3 | 对照 Plan Finder 校准误差；完成 2–3 个家属访谈，记录原话 | 误差报告 + 访谈笔记 |
| 9 | 周日 10/4 | 把引擎包成 agent tools（JSON in/out）；在 Token Factory Sandbox 里跑通一次；开始写 friction log | Sandbox 可调用的工具集 |

**Gate 1（周日晚）：** 10 个 persona 中 ≥ 8 个误差 ≤ 10%，并且工具能在 Sandbox 里跑。

## Week 2（10/5–10/11）：Agent loop + 文档抽取 + memory

本周让 Nemotron 把工具串起来：从上传的文件到一份结构化的决策包，先用 CLI 跑通，暂不做 UI。

| Day | 日期 | 任务 | 产出 |
| --- | --- | --- | --- |
| 10 | 周一 10/5 | 定 agent 架构：planner（Super）+ tools + 校验重试；所有输出强制 JSON schema | Agent 骨架 |
| 11 | 周二 10/6 | Nano Omni 读药瓶照片 → 结构化药单（准备 10 张测试图） | `extract_meds` |
| 12 | 周三 10/7 | 读 ANOC PDF → 抽取变化项；与当前计划做 diff（下载 3–5 份真实 ANOC） | `anoc_diff` |
| 13 | 周四 10/8 | 红旗规则：SEP（计划退出）、Medigap 回头路、Extra Help、Prescription Payment Plan、SNP 资格（C-SNP / D-SNP）、prior auth / step therapy；规则代码化，Ultra 只负责解释 | `red_flags` |
| 14 | 周五 10/9 | Persistent memory：用户 profile（药单、医生、药房、历次决定），用 SQLite 或 Postgres | Memory 层 |
| 15 | 周六 10/10 | 医生网络核实：NPPES + 1–2 家大保险公司的 FHIR directory；输出置信度 + 电话核实脚本 | `check_network` |
| 16 | 周日 10/11 | 端到端跑 10 个 persona；修 tool-calling 失败；记录成功率 | CLI MVP + eval v1 |

**Gate 2（周日晚）：** 端到端成功率 ≥ 80%。达不到 → 砍掉 `check_network`，改成只生成电话核实脚本。

## Week 3（10/12–10/18）：UI + 部署 + Tavily，10/18 feature freeze

本周把 CLI 变成一个评委能打开的 demo URL。Design 占 25% 的分，这是你设计背景的主场。AEP 于 10/15 开始，也是最适合找真实用户试用的时间。

| Day | 日期 | 任务 | 产出 |
| --- | --- | --- | --- |
| 17 | 周一 10/12 | 在 Canva / Figma 里画 4 个页面的线框图：上传 → agent 工作 → 结果 → 家人总结；大字体、高对比度 | 线框图 |
| 18 | 周二 10/13 | 前端：上传页 + 结果页（计划排名、成本拆分图） | 前端 v1 |
| 19 | 周三 10/14 | Agent 工作页：streaming 显示每一步、工具调用和来源链接 | Trace 可视化 |
| 20 | 周四 10/15 | Tavily：查 star rating、计划退出新闻和最新变更，反哬到红旗和排名里（要是 load-bearing，不是装饰） | `web_research` |
| 21 | 周五 10/16 | 部署：前端放 Vercel，后端选 scale-to-zero 的平台，推理走 Token Factory；配置一个公开 demo 账号 | 线上 demo URL |
| 22 | 周六 10/17 | 家人总结页 + 分享链接；请 1–2 位访谈过的家属试用，记录反馈 | 完整流程 |
| 23 | 周日 10/18 | 修试用中发现的 top 5 问题；跑 eval v2；**feature freeze** | v1.0 |

**Gate 3（周日晚）：** 陌生人能在不看说明的情况下走完整个流程。这之后只修 bug，不加功能。

## Week 4（10/19–10/25）：2027 数据 + polish + 视频 + 文档

本周不写新功能，把所有提交材料做完。视频是评委最先看到的东西，给它留足两天。

| Day | 日期 | 任务 | 产出 |
| --- | --- | --- | --- |
| 24 | 周一 10/19 | 检查 CMS 有没有发布 2027 数据：有就切换并重跑 eval，没有就在 UI 里标注“基于 2026 数据” | 数据版本确定 |
| 25 | 周二 10/20 | 视频脚本（< 3 min）：0–20s 痛点 + Rosa 的故事 → 演示 → 技术架构 30s → impact 数字；分镜头清单 | 脚本 |
| 26 | 周三 10/21 | README（setup、架构图、testing instructions）+ MIT license；清理 repo | Repo ready |
| 27 | 周四 10/22 | 录屏 + 配音；多录几遍，挑最顺的 | 视频粗剪 |
| 28 | 周五 10/23 | Devpost 文案：项目描述、Nebius / NVIDIA 怎么帮了你、把 friction log 整理成 feedback | 文案草稿 |
| 29 | 周六 10/24 | 剪辑定稿、加字幕、上传 YouTube（public）；封面和截图用 Canva 做 | 视频定稿 |
| 30 | 周日 10/25 | 全流程整体审查：用无痕窗口走一遍 demo，按 4 项评分标准自评打分 | 提交包完整 |

## Final（10/26–10/30）：提交与 buffer

10/28 提交，剩下两天纯粹是保险。

- **10/26（周一）：** 修审查中发现的问题；确认 demo URL 和 demo 账号能正常使用
- **10/27（周二）：** 在 Devpost 填完所有字段，保存为草稿
- **10/28（周三）：** 提交。记得勾选 Personal AI track 和 Tavily bonus，并填上 city
- **10/29–10/30：** 只在出问题时修改。截止前还可以编辑提交内容
- **评审期到 12/15：** demo 必须一直在线；每周检查一次 API 额度和账单

## 风险与预算

最大的风险是数据准确度和工作日精力。每个 Gate 没过，就立刻砍范围，不延期。

| 风险 | 应对 |
| --- | --- |
| 成本计算误差过大 | 改为显示排名 + 费用区间，并明确写出假设 |
| 2027 数据来不及 | 数据层按 plan year 替换；实在来不及就用 2026 数据并标注 |
| Nemotron tool calling 不稳 | 工具设计得更小、强制 schema + 重试；把关键流程改成确定性编排 |
| 医生网络数据不准 | 显示置信度 + 电话核实脚本；必要时砍掉 |
| 工作日太累、进度落后 | 每周日 Gate 时对照范围砍功能；优先保证 demo 故事完整 |
| 雇主 IP / conflict of interest | Week 0 就查合同；只用公开数据，用个人设备、个人时间开发 |

**预算（估算）：**

- Nebius / Tavily：$0–50（先用掉 $50 免费 credits）
- Claude：继续用 Pro。如果 W2–W3 每周撞限额 2 次以上，就升级一个月 Max 5x（约 $100）
- 托管：选免费或 scale-to-zero 的方案，要撑到 12/15
- **最坏情况合计约 $150**
