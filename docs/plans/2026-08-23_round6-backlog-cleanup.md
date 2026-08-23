# OmniDesk R6 遗留项清尾计划

> 日期:2026-08-23 | 状态:**待实施**
> 起源:R5 收官后计划文档「留给后续轮次的遗留项」4 条 + T5 reviewer MEDIUM 发现,合并为本轮清尾。
> 关联:R5(`docs/plans/2026-08-20_project-optimization-round5.md`,20/20 完成)

## 1. 背景

R5 全部 20 项已合并(#393~#430)。本轮回收 5 个小规模遗留项,均为 XS~S 工作量,
目标一个批次内完成。

## 2. 任务清单(按风险从低到高排序)

### R6-1 observability 遗留清理(XS)
- `core/tests/test_observability_logger.py` 的 BASELINE 清单在 R5-B7 迁移后已成
  冗余(30 文件全部走 get_logger,BASELINE 恒绿无信息量)——删除 BASELINE 测试或
  改为守卫脚本互证
- `events/tasks.py` 的 `_obs_logger = get_logger(__name__)` 与新 `logger` 等价,
  合并为单一 logger(检查引用点后删旧名)
- **验证**:pytest core/tests/ + events/;ruff

### R6-2 scope 回归测试虚过修复(XS,T5 reviewer MEDIUM)
`test_tool_scope_regression.py` 两测试虚过(fixture 缺陷):
- project:名称"B的秘密项目ZXC"含 stopwords"项目",extract 后关键词变"秘密ZXC",
  icontains 不命中 → 改名避开停用词(如"B的绝密工程ZXC")
- schedule:ISO 日期字符串"2026-08-30 值班"不被解析(target 恒今天)→ 改用
  `timezone.now().date()` 创建数据 + query 用"今天 值班"
- **验收标准(TDD)**:修复后的 fixture 在 R5-D1 合并前的 main 提交上跑必须 RED
  (reviewer 已实证旧路径确实泄露),当前 main 上 GREEN
- **验证**:pytest smart_assistant/tests/test_tool_scope_regression.py

### R6-3 res.data.results 散点收口(S)
41 处散点/23 文件。统一改用 `extractResults`(shared/api/responseHandler.js,
R5-D6 已交付):
- api 层文件(personnelApi/scheduleApi)优先——收敛后 hook/组件层自动干净
- 页面组件直取处逐文件替换;测试文件的 mock 断言相应适配
- 不强求 100%:动态结构(如非分页裸数组语义明确处)可保留并注释
- **验证**:npx jest --silent 全绿 + lint;grep 残留计数报告

### R6-4 react-router 6.30.4→7.18.2 升级(M)
2 个 moderate(CVE-2025-68470 bypass + SSR 反序列化注入),6.x 无补丁版
(6.30.6 仍在漏洞范围 6.0.0-7.17.0),唯一修复路径是 major 升级。
- **兼容性预判(已核实)**:项目 API 使用面(BrowserRouter/createBrowserRouter/
  Link/useNavigate/Outlet/MemoryRouter/Routes)在 v7 全部保留;Node >=20 要求满足
  (CI Node 20 / 本机 25);React 18.3 满足;browserslist chrome>=109 由 Vite 转译保障
- **Windows 7 红线**:升级后 build 产物需验证无 ES2022+ 泄出(browserslist 已限 109)
- **风险点**:v7 对 `<Routes>` 子元素写法更严格(不能有非 Route 子节点)、
  future flags 默认化——jest 全量 + build + audit 清零兜底
- **验证**:npx jest --silent + npm run lint + npm run build + npm audit 清零

### R6-5 裸 Table 全量迁移 + lint 禁令(S~M)
38 个 feature 文件仍用裸 `<Table>`。R5-D4 已扩展 DataTable(actionAlign/
rowSelection/extraColumns)并沉淀样板页经验(showActions=false 统一、pagination
显式化陷阱):
- 分两批迁移:批1 = 与已改造页面同域的约半数;批2 = 其余
- 每页行为红线:列定义/排序/分页/选择对外不变;DataTable 默认 pagination=false,
  原依赖 antd 默认分页的页显式 pagination={{pageSize:10}}
- 完成后 `.eslintrc.json` 加 no-restricted-imports 禁 `import { Table } from 'antd'`
  (白名单 DataTable/SkeletonTable 定义文件与确需原生 Table 的特例)
- **验证**:每批 npx jest --silent + lint + build;routes.json 漂移还原不提交

## 3. 实施顺序与节奏

1→2→3→4→5(低风险先行;各项独立 PR,单项失败不阻塞其他)
沿用 R5 节奏:独立 PR + CI 监控 + squash merge;网关不稳时主会话直接实施。

## 4. 风险

- R6-4 是唯一 major 依赖升级,jest/build 双绿 + audit 清零为验收线;若 v7 有隐性
  breaking(运行时才暴露),回滚该单项不阻塞其他任务
- R6-5 批量大,严格按域分组小步提交;任何一页行为等价存疑即停下核对

## 实施步骤

- [ ] R6-1 observability 遗留清理(BASELINE 删除 + _obs_logger 合并)
- [ ] R6-2 scope 回归测试虚过修复(project/schedule fixture)
- [ ] R6-3 res.data.results 散点收口(41 处/23 文件)
- [ ] R6-4 react-router v7 升级(audit 清零)
- [ ] R6-5 裸 Table 全量迁移(38 文件)+ lint 禁令
