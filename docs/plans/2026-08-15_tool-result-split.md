# R3-D2: ToolResult.jsx 拆分实施计划

> 日期:2026-08-15 | 状态:已完成 | 关联:round3 计划 `docs/plans/2026-08-14_project-optimization-round3.md` R3-D2
> 模式:复用 R3-D1 同款 SDD 拆分流程 —— 拆文件 + 逐字搬运 + repoint + 差分验证;目录结构沿用 R3-D1(`utils/` + `components/`)

## 1. 背景与目标

### 背景

`omni_desk_frontend/src/features/smart-assistant/components/ToolResult.jsx` 当前 **588 行**,单文件承担 4 类职责:

| 职责 | 位置 | 行数 |
|---|---|---|
| `FileDownloadCard`(office 文件下载卡片) | L15-56 | ~42 |
| 纯函数:`normalizeAggregatedResult` / `serializeResult`(12 个 intent 分支的复制文本策略) | L63-177 | ~115 |
| `ResultCardWrapper`(通用结果卡片包装器) | L183-197 | ~15 |
| `ToolResult` 主组件:intent 分发(12 个分支)+ copy 按钮 + 兜底(file_download / !found / null) | L199-486 | ~288 |
| propTypes(公开契约) | L490-588 | ~99 |

所有 intent 分支共享 `div.tool-result-card > Card + 复制按钮` 骨架,大量 `result.X.map(item => <Descriptions>...)` 重复结构。round3 计划明确列为 R3-D2,修复方向:**按工具类型拆分子组件 + 注册中心**。

**对外契约(必须零变化):**
- 被引用方:`src/shared/components/QuickAssistant.jsx`(2 处)、`src/features/smart-assistant/components/MessageList.jsx`(2 处),均为 `render(<ToolResult intent result sources />)`
- 测试:`__tests__/ToolResult.test.jsx`(aggregated_day 渲染 6 用例)、`__tests__/ToolResult.download.test.jsx`(下载卡片 2 用例),均 `import ToolResult from '../ToolResult'`,零 repoint

### 目标

1. 将 `ToolResult.jsx` 拆为**薄壳(~90 行)** + 注册中心 + 13 个子组件 + 2 个 utils,各新文件 <120 行、函数 <50 行
2. **对外契约零变化**:默认导出 `ToolResult`、props `{intent, result, sources}`、import 路径全部不变 → 4 处调用方 + 2 个测试套件零改动
3. 拆分行为逐字一致,经 2 个测试套件(8 用例)全量回归 + 差分验证
4. 新增 1 个 intent 渲染冒烟测试,补齐 10 个无覆盖 intent 分支的回归守卫(aggregated_day / download 已有覆盖)

## 2. 涉及的文件与模块

### 新增(18 个)

#### utils(2 个)—— 纯函数,不依赖 React

| 文件 | 职责 | 预估行数 |
|---|---|---|
| `smart-assistant/utils/normalizeAggregatedResult.js` | aggregated_day 结果规范化(扁平结构 + 兼容 `{data:}` 包层) | ~12 |
| `smart-assistant/utils/serializeResult.js` | 12 个 intent 分支的复制文本序列化(import normalizeAggregatedResult) | ~100 |

#### components/toolResults/(15 个)—— 按工具类型拆分子组件 + 注册中心

| 文件 | 职责 | 预估行数 |
|---|---|---|
| `toolResults/ResultCardWrapper.jsx` | 共享包装器:`div.tool-result-card > Card(Tag) + copyBtn` | ~17 |
| `toolResults/FileDownloadCard.jsx` | office 文件下载卡片(原 L15-56 逐字搬移) | ~50 |
| `toolResults/AggregatedDayResultCard.jsx` | aggregated_day 分支包装(normalize → 复用现有 `AggregatedDayCard`) | ~15 |
| `toolResults/ScheduleResultCard.jsx` | schedule_query 排班信息(blue) | ~35 |
| `toolResults/PersonnelResultCard.jsx` | personnel_query 人员信息(green) | ~45 |
| `toolResults/KnowledgeQaCard.jsx` | knowledge_qa 引用来源(purple,用 `sources` prop) | ~30 |
| `toolResults/DocumentSearchCard.jsx` | document_search 文档搜索(orange) | ~40 |
| `toolResults/EventQueryCard.jsx` | event_query 事件/日程(magenta,schedules + holidays 两段) | ~50 |
| `toolResults/MemoQueryCard.jsx` | memo_query 备忘录(cyan) | ~45 |
| `toolResults/ProjectStatusCard.jsx` | project_status 项目信息(volcano) | ~40 |
| `toolResults/AnnouncementQueryCard.jsx` | announcement_query 公司公告(geekblue) | ~40 |
| `toolResults/ComplianceQueryCard.jsx` | compliance_query 合规问题(red,severity/status Tag) | ~55 |
| `toolResults/ExternalLinkQueryCard.jsx` | external_link_query 内网外链(cyan,SSO 链接) | ~50 |
| `toolResults/NewsSearchCard.jsx` | news_search 新闻/通知(gold) | ~40 |
| `toolResults/registry.js` | 注册中心:intent → `{ component, when }`(when 为分发守卫,精确镜像现行分支条件) | ~35 |

### 修改(1 个)

| 文件 | 改动 |
|---|---|
| `components/ToolResult.jsx` | 588 → ~90 行薄壳:copy 按钮 + 注册中心分发 + 兜底(file_download / !found / null),保留完整 propTypes 与 `ToolResult.css` import |

### 新增测试(1 个)

| 文件 | 职责 |
|---|---|
| `components/__tests__/ToolResult.intents.test.jsx` | 冒烟测试:遍历注册中心渲染每个 intent 示例数据,断言标题 Tag + 无崩溃 |

### 不变(5 个)

| 文件 | 说明 |
|---|---|
| `components/AggregatedDayCard.jsx` | 自包含组件(纯 antd),被 `AggregatedDayResultCard` 复用,不动 |
| `ToolResult.css` | 46 行 / 3 类(`tool-result-card` / `sources-list` / `tool-copy-btn`),由薄壳统一 import,子组件复用 class(同 R3-D1 CSS 策略) |
| 4 处调用方(QuickAssistant ×2 / MessageList ×2) | `import ToolResult from '../ToolResult'` 路径不变 |
| 2 个既有测试套件 | `import ToolResult from '../ToolResult'` 零 repoint |
| `api/smartAssistantApi.js`(`downloadOfficeFile`) | 被 FileDownloadCard 复用,不变 |

## 3. 技术方案(架构/接口设计)

### 3.1 模块职责划分

```
ToolResult.jsx(薄壳 ~90 行)
  ├── state: copied(useState)
  ├── handleCopy → serializeResult(intent, result, sources)(utils)
  ├── copyBtn(复用导出)
  ├── if (!result) return null
  ├── 注册中心分发:
  │     const entry = TOOL_RESULT_REGISTRY[intent];
  │     if (entry && entry.when(result, sources))
  │       return <entry.component result sources copyBtn />
  ├── 兜底链(顺序与现行一致):
  │     ① !result.found → <Tag>{message || '未找到相关信息'}</Tag>
  │     ② result.file_download → <Card>生成文件</Card> + <FileDownloadCard>
  │     ③ return null
  └── 保留完整 propTypes + import './ToolResult.css'

toolResults/registry.js(注册中心)
  └── intent → { component, when }
      aggregated_day:   when = () => true               # 恒渲染(空态由 AggregatedDayCard 内部兜底)
      schedule_query:   when = r => r.found
      personnel_query:  when = r => r.found
      knowledge_qa:     when = (r, sources) => sources?.length > 0
      document_search:  when = r => r.found && r.documents
      event_query:      when = r => r.found
      memo_query:       when = r => r.found && r.memos
      project_status:   when = r => r.found && r.projects
      announcement_query: when = r => r.found && r.posts
      compliance_query: when = r => r.found && r.issues
      external_link_query: when = r => r.found && r.links
      news_search:      when = r => r.found && r.articles
```

### 3.2 子组件统一契约

每个 intent 卡片接收 `{ result, sources, copyBtn }`(knowledge_qa 用 `sources`,其余用 `result`),内部按现行 JSX 逐字搬移,返回 `ResultCardWrapper`(aggregated_day 除外,返回裸 `div.tool-result-card`)。

### 3.3 注册中心分发语义保真(关键)

现行分发是**顺序 if 链 + 兜底**;重构后改为 **when 守卫 + 兜底链**,两者语义等价:

- 每个分支的条件(`result.found` / `result.documents` / `sources?.length` 等)精确映射为注册中心 `when` 守卫 → 守卫不通过时**自然落回**兜底链(与现行短路行为一致)
- `aggregated_day` 恒渲染(`when: () => true`),空态 `{summary: '未找到相关信息', ...}` 由 AggregatedDayCard 内部 Empty 处理(测试已验证)
- 兜底链顺序严格保持 `!found` → `file_download` → `null`,确保 `office_generate` 等未知 intent 的文件下载卡必定呈现

### 3.4 逐字搬运原则

- 纯函数(`normalizeAggregatedResult` / `serializeResult`)逐字搬入 `utils/`,export 调整
- `FileDownloadCard` / `ResultCardWrapper` 逐字搬入 `toolResults/`,仅 export 调整
- 12 个 intent 分支 JSX 逐字搬入对应卡片,propTypes 按各卡片使用的数据切片精简定义;`ToolResult` 完整 propTypes 保留在薄壳(公开契约)
- **不改语义**:条件渲染、Badge 状态色映射、链接 target/rel、event_query 两段式 Descriptions、copy 按钮的静默失败 catch 全部保留

## 4. 实施步骤

### Task 1: 新增 2 个 utils

- [x] `utils/normalizeAggregatedResult.js` — 逐字搬运 + export
- [x] `utils/serializeResult.js` — 逐字搬运 + import normalizeAggregatedResult + export

### Task 2: 新增 3 个共享子组件

- [x] `toolResults/ResultCardWrapper.jsx` — 逐字搬移 + propTypes
- [x] `toolResults/FileDownloadCard.jsx` — 逐字搬移 + propTypes
- [x] `toolResults/AggregatedDayResultCard.jsx` — aggregated_day 分支包装(normalize → AggregatedDayCard)

### Task 3: 新增 11 个 intent 卡片 + 注册中心

- [x] ScheduleResultCard / PersonnelResultCard / KnowledgeQaCard / DocumentSearchCard
- [x] EventQueryCard / MemoQueryCard / ProjectStatusCard / AnnouncementQueryCard
- [x] ComplianceQueryCard / ExternalLinkQueryCard / NewsSearchCard
- [x] `toolResults/registry.js` — intent → `{ component, when }`(when 精确镜像现行分发条件)
- [x] 每卡片逐字搬移对应分支 JSX + 精简 propTypes

### Task 4: 重构 `components/ToolResult.jsx` 为薄壳

- [x] copy 按钮 + 注册中心分发 + 兜底链(!found → file_download → null)
- [x] 保留完整 propTypes(公开契约)与 `ToolResult.css` import
- [x] 确认 4 处调用方 import 路径零改动

### Task 5: 新增冒烟测试 + 验证

- [x] 新增 `__tests__/ToolResult.intents.test.jsx` — 遍历注册中心渲染示例数据,断言标题 Tag 存在
- [x] 2 个既有测试套件**零改动**通过(baseline 8 passed)
- [x] `npm test` 全量回归绿(与 baseline 对比)
- [x] `npm run lint` 通过
- [x] `npm run build` 通过(generate-routes + vite build)

### Task 6: 文档更新 + PR + merge

- [x] round3 plan 标注 R3-D2 完成
- [x] feature 分支 push → PR → CI 监控 → merge → 清理(按 R3-D1 先例)

## 5. 验收标准

| 标准 | 验证方式 |
|---|---|
| `ToolResult.jsx` 薄壳化 | `wc -l`(实际 174 行 = ~76 行组件逻辑 + 98 行保留 propTypes 公开契约;若剔除 propTypes 则 ≤100 达标) |
| 各新文件 <120 行 / 函数 <50 行 | `wc -l` + 目检(serializeResult 92 行例外,逐字搬运保留,见风险表) |
| 2 个既有测试套件零改动通过 | `npx jest components/__tests__/ToolResult` |
| 全量 jest / lint / build 三绿 | `npm test` + `npm run lint` + `npm run build` |
| 4 处调用方 import 路径不变 | `git diff` |
| 注册中心覆盖 12 个 intent + 兜底链顺序保持 | 目检 registry.js + 冒烟测试 |

## 6. 风险评估与依赖

| 风险 | 缓解 |
|---|---|
| **高**:注册中心分发改变短路顺序 → 兜底渲染回归(如 schedule_query 未 found 时错误渲染 file_download 卡) | `when` 守卫精确镜像现行条件;兜底链顺序硬编码与现行一致;8 用例回归 + 新增冒烟测试覆盖 12 个 intent |
| **中**:子组件 props 传错(无 TypeScript) | 统一契约 `{result, sources, copyBtn}` + 逐字搬运 + 冒烟测试兜底 |
| **中**:新目录 `toolResults/` 与既有 flat 结构不一致 | 12+ 新文件放 flat 会膨胀 `components/`;子目录按功能聚合,是 MANY SMALL FILES 原则的自然延伸 |
| **低**:CSS class 依赖薄壳 import | 单一 `ToolResult.css` 由薄壳引入,子组件复用 class(同 R3-D1 先例) |
| **低**:行数指标例外 | `serializeResult.js` 92 行 / `ToolResult.jsx` 174 行,均为**逐字搬运 + 保留公开契约**所致(重构未新增逻辑);拆分目标「降单文件复杂度」已达成(588 → 最大 92 行逻辑文件) |

## 7. 关联

- 上游:`docs/plans/2026-08-14_project-optimization-round3.md`(R3-D2)
- 同源:R3-D1(`docs/plans/2026-08-15_smart-chat-page-split.md`,同款逐字搬运 + repoint + 差分验证流程)、后端 R3-A4(`chat.py` 拆分)
- 技术文档:`docs/technical/32-smart-assistant-multi-agent.md`(前端模块表,可选更新)
