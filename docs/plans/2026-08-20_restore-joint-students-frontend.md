# 联培生模块前端恢复 + 文档归档 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从零创建 19 个前端文件(6 API + 9 页面 + 2 组件 + 1 路由测试 + 1 个共享导航项),实现联培生管理模块的 4 角色前端(管理员/专家/联培生/导师),与已完成的后端 API 联调,Jest 覆盖率 ≥ 80%,CI 全绿后合并到 main。

**Architecture:** 严格复用现有 `features/personnel/` 的目录约定(`api/components/pages` + 每文件配 jest 测试),使用 Ant Design 5 + TanStack React Query + Axios(JWT 拦截自动 token 刷新),所有路由走 `ProtectedRoute` + `PageRoute` 权限保护(后端 migration 0003 已注册 12 个 PageRoute),`__tests__` 加 1 个路由快照测试。

**Tech Stack:** React 18.3 + React Router 6.4+ (createBrowserRouter) + Ant Design 5 + TanStack React Query v5 + Axios + Jest + @testing-library/react。

## Global Constraints(项目 + 全局规则硬约束)

- **Python/Django/file 字段不在本 PR 范围**(后端已合并 PR #391)
- **plan 文档归档**:`docs/plans/` 仅留进行中;完成后并入 `docs/technical/37-joint-students-module.md` §前端章节,并**删除本 plan**
- **所有 commit 走 conventional commits**(`feat:` / `fix:` / `test:` / `docs:` / `chore:`)
- **feature 分支**:`feat/restore-joint-students-frontend`,从 `main` 切,**永远不在 main 上直接 commit**
- **commit 间隔**:每个 Task 单独 commit,确保 bisect 可行
- **测试覆盖率**:Jest `--coverage` 必须 ≥ 80% 行/分支(per testing.md 最低要求)
- **CI 必须 9/9 jobs pass** 才允许 merge(见 `.github/workflows/ci.yml`)
- **Windows 7 + Chrome 109 兼容**:不用 `:has()` / container queries / ES2022+ 语法;Vite build 目标已配置
- **离线优先**:不引外部 CDN,所有依赖 npm 锁定
- **语言中文**:progress / commit / PR / docs / 评论 一律中文,代码标识符 / Ant Design 英文组件名保留
- **样式**:仅 Ant Design 5(120 imports 已确认),不引 MUI;**禁止** `console.log` / 调试代码
- **状态**:TanStack React Query staleTime 5 min,refetchOnWindowFocus false(与现有约定一致)
- **类型**:JSDoc 注释给关键 props / API 响应,不强求 TypeScript(项目是 JS + 部分 .jsx)
- **后端契约**:API 路径、字段、状态机、权限矩阵定义于 `docs/superpowers/specs/2026-07-28-联培生管理模块-design.md` §API 设计/§权限模型/§数据模型

## 涉及的 19 个新文件 + 7 个修改文件

### 新增(`omni_desk_frontend/src/features/joint-students/`)

| 编号 | 路径 | 类别 | 复杂度 |
|---|---|---|---|
| F1 | `api/client.js` | axios + JWT 拦截工厂 | 中 |
| F2 | `api/students.js` | 联培生 CRUD | 低 |
| F3 | `api/reports.js` | 月度报告 + 状态机 | 中 |
| F4 | `api/cycles.js` | 考核批次 + 强制截止 | 中 |
| F5 | `api/scores.js` | 专家打分 + 解锁 | 中 |
| F6 | `api/stipends.js` | 补助复核 + 锁定 | 中 |
| F7 | `components/GradeBadge.jsx` | A/B 档徽章 | 低 |
| F8 | `components/StipendBreakdown.jsx` | 补助明细展示 | 中 |
| F9 | `pages/admin/StudentListPage.jsx` | 联培生列表 + 筛选 | 中 |
| F10 | `pages/admin/StudentEditPage.jsx` | 创建/编辑 | 中 |
| F11 | `pages/admin/ReportReviewPage.jsx` | 报告审核 | 中 |
| F12 | `pages/admin/CycleManagementPage.jsx` | 批次管理 | 中 |
| F13 | `pages/admin/StipendReviewPage.jsx` | 补助复核 | 中 |
| F14 | `pages/expert/ExpertScoringPage.jsx` | 专家打分 | 中 |
| F15 | `pages/student/MyReportsPage.jsx` | 我的月度报告 | 中 |
| F16 | `pages/student/MyStipendsPage.jsx` | 我的补助 | 中 |
| F17 | `pages/mentor/MentorOverviewPage.jsx` | 导师视图 | 中 |
| F18 | `__tests__/routes.test.jsx` | 路由快照 + 角色访问 | 低 |
| F19 | `api/index.js` | 聚合 re-export | 低 |

### 修改

| 路径 | 改动 | commit |
|---|---|---|
| `src/routes/lazyImports.js` | 加 9 个 lazy import 行(9 个 page) | M1 |
| `src/routes/index.jsx` | 注册 13 条路由(角色权限编码) | M2 |
| `src/shared/components/sidebar/Sidebar.jsx` | 加"联培生管理"菜单 + 子菜单按角色 | M3 |
| `docs/technical/37-joint-students-module.md` | 补 §前端章节 + 接口定义表 | M4 |
| `docs/technical/README.md` | 章节 37 状态从"后端" → "前端+后端" | M5 |
| `docs/user-manual/07-joint-students.md` | 新建(用户操作手册) | M6 |
| `docs/user-manual/README.md` | 章节 07 加入目录 | M7 |

## 实施步骤(6 阶段 / 24 个 Task)

---

### Phase 1 — 脚手架(feature 分支 + API 客户端)

#### Task 1: 建 feature 分支 + 写 plan 文档

**Files:**
- Create: `docs/plans/2026-08-20_restore-joint-students-frontend.md`(本文件)

**Step 1: 切分支**

```bash
git fetch origin main
git switch -c feat/restore-joint-students-frontend origin/main
```

**Step 2: 确认分支**

```bash
git branch --show-current
# 期望: feat/restore-joint-students-frontend
```

**Step 3: Commit plan**

```bash
git add docs/plans/2026-08-20_restore-joint-students-frontend.md
git commit -m "docs(plan): 联培生前端模块 19 文件 + 13 路由 + 3 共享修改 实施计划"
```

---

#### Task 2: API client 工厂(F1)

**Files:**
- Create: `omni_desk_frontend/src/features/joint-students/api/client.js`
- Create: `omni_desk_frontend/src/features/joint-students/api/client.test.js`

**Step 1: 写测试**

```javascript
// client.test.js
import { createJointStudentsClient } from './client';

describe('createJointStudentsClient', () => {
  const mockAxios = {
    interceptors: { request: { use: jest.fn() }, response: { use: jest.fn() } },
    get: jest.fn(), post: jest.fn(), patch: jest.fn(), delete: jest.fn(),
  };

  it('createJointStudentsClient 返回带 baseURL /api/joint-students/ 的 axios 实例', () => {
    const client = createJointStudentsClient(mockAxios);
    expect(mockAxios.interceptors.request.use).toHaveBeenCalled();
    expect(mockAxios.interceptors.response.use).toHaveBeenCalled();
  });
});
```

**Step 2: 实现**

```javascript
// client.js
import axios from 'axios';

export const createJointStudentsClient = (instance = axios) => {
  const client = instance.create({
    baseURL: '/api/joint-students/',
    timeout: 30000,
  });
  // JWT 拦截:与 omni_desk_frontend/src/shared/api/axiosConfig.js 保持一致
  client.interceptors.request.use((config) => {
    const token = localStorage.getItem('access_token');
    if (token) config.headers.Authorization = `Bearer ${token}`;
    return config;
  });
  client.interceptors.response.use(
    (r) => r,
    async (err) => {
      if (err.response?.status === 401) {
        localStorage.removeItem('access_token');
        window.location.href = '/login';
      }
      return Promise.reject(err);
    }
  );
  return client;
};

export default createJointStudentsClient();
```

**Step 3: 跑测试**

```bash
cd omni_desk_frontend && npm test -- --testPathPattern=joint-students/api/client
# 期望: 1 passed
```

**Step 4: Commit**

```bash
git add src/features/joint-students/api/client.js src/features/joint-students/api/client.test.js
git commit -m "feat(joint-students): API client 工厂 + JWT 拦截"
```

---

#### Task 3-7: 5 个 API 模块(F2-F6)

**Files:**(每个 Task 一个 API + 测试)

- Task 3 → `api/students.js` + `students.test.js`
- Task 4 → `api/reports.js` + `reports.test.js`
- Task 5 → `api/cycles.js` + `cycles.test.js`
- Task 6 → `api/scores.js` + `scores.test.js`
- Task 7 → `api/stipends.js` + `stipends.test.js`

**通用契约**:**每个** API 文件包含以下标准的 CRUD 包装:

```javascript
// students.js 模板
import client from './client';

export const listStudents = (params) => client.get('students/', { params });
export const getStudent = (id) => client.get(`students/${id}/`);
export const createStudent = (data) => client.post('students/', data);
export const updateStudent = (id, data) => client.patch(`students/${id}/`, data);
export const graduateStudent = (id) => client.post(`students/${id}/graduate/`);
```

**每个 API 测试模式**(针对 reports.js 例子,其他文件照搬):

```javascript
// reports.test.js
import * as reports from './reports';

jest.mock('./client', () => ({
  __esModule: true,
  default: {
    get: jest.fn(), post: jest.fn(), patch: jest.fn(),
  },
}));
import client from './client';

describe('reports API', () => {
  it('listReports 调用 GET reports/', () => {
    reports.listReports({ year: 2026, month: 8 });
    expect(client.get).toHaveBeenCalledWith('reports/', { params: { year: 2026, month: 8 } });
  });
  it('submitReport 调用 POST reports/{id}/submit/', () => {
    reports.submitReport(42);
    expect(client.post).toHaveBeenCalledWith('reports/42/submit/');
  });
});
```

**全量 API 端点函数清单**(以 API 设计 §全部路径为准):

| 文件 | 函数 | 端点 |
|---|---|---|
| `students.js` | `listStudents` / `getStudent` / `createStudent` / `updateStudent` / `graduateStudent` | `students/` |
| `reports.js` | `listReports` / `getReport` / `createReport` / `updateReport` / `submitReport` / `approveReport` / `rejectReport` / `withdrawReport` | `reports/` |
| `cycles.js` | `listCycles` / `getCycle` / `createCycle` / `forceCloseCycle` / `listCycleScores` / `listCycleStipends` | `cycles/` |
| `scores.js` | `createScore` / `getScore` / `unlockScore` / `resubmitScore` | `scores/` |
| `stipends.js` | `listStipends` / `getStipend` / `lockStipend` | `stipends/` |

**Step 1**:写测试 → **Step 2**:实现 → **Step 3**:`npm test -- --testPathPattern=features/joint-students/api` → **Step 4**:commit

**Commit 模板**(每个 Task 一个):

```bash
git commit -m "feat(joint-students): reports API 客户端 + mock 单元测试"
```

---

#### Task 8: API 聚合 re-export(F19)

**Files:**
- Create: `omni_desk_frontend/src/features/joint-students/api/index.js`

**Step 1: 实现**

```javascript
// api/index.js
export * from './students';
export * from './reports';
export * from './cycles';
export * from './scores';
export * from './stipends';
```

**Step 2: Commit**

```bash
git add src/features/joint-students/api/index.js
git commit -m "feat(joint-students): API 聚合入口"
```

---

### Phase 2 — 共享组件 + 路由 + 菜单(贯穿所有页面)

#### Task 9: 共享组件 — GradeBadge(F7)

**Files:**
- Create: `omni_desk_frontend/src/features/joint-students/components/GradeBadge.jsx`
- Create: `omni_desk_frontend/src/features/joint-students/components/GradeBadge.test.jsx`

**Step 1: 写测试**

```jsx
// GradeBadge.test.jsx
import { render, screen } from '@testing-library/react';
import GradeBadge from './GradeBadge';

describe('GradeBadge', () => {
  it('grade="A" 渲染绿色标签 + "A 档"', () => {
    render(<GradeBadge grade="A" />);
    expect(screen.getByText('A 档')).toBeInTheDocument();
  });
  it('grade="B" 渲染灰色标签 + "B 档"', () => {
    render(<GradeBadge grade="B" />);
    expect(screen.getByText('B 档')).toBeInTheDocument();
  });
});
```

**Step 2: 实现**

```jsx
// GradeBadge.jsx
import { Tag } from 'antd';

/**
 * 联培生考核档次徽章
 * @param {{ grade: 'A' | 'B' }} props
 */
export default function GradeBadge({ grade }) {
  if (grade === 'A') return <Tag color="green">A 档</Tag>;
  if (grade === 'B') return <Tag color="default">B 档</Tag>;
  return <Tag>未评定</Tag>;
}
```

**Step 3: 跑测试 + Commit**

```bash
npm test -- --testPathPattern=components/GradeBadge
git add src/features/joint-students/components/GradeBadge.jsx src/features/joint-students/components/GradeBadge.test.jsx
git commit -m "feat(joint-students): GradeBadge A/B 档徽章组件"
```

---

#### Task 10: 共享组件 — StipendBreakdown(F8)

**Files:**
- Create: `omni_desk_frontend/src/features/joint-students/components/StipendBreakdown.jsx`
- Create: `omni_desk_frontend/src/features/joint-students/components/StipendBreakdown.test.jsx`

**Step 1: 写测试**

```jsx
// StipendBreakdown.test.jsx
import { render, screen } from '@testing-library/react';
import StipendBreakdown from './StipendBreakdown';

const fixture = {
  base_amount: '6000.00',
  grade_coefficient: '0.80',
  attendance_ratio: '0.50',
  final_amount: '2400.00',
  student_type: 'phd',
  grade: 'B',
};

describe('StipendBreakdown', () => {
  it('展示基本额度 / 系数 / 出勤比 / 最终金额', () => {
    render(<StipendBreakdown record={fixture} />);
    expect(screen.getByText(/6000/)).toBeInTheDocument();
    expect(screen.getByText(/0\.80/)).toBeInTheDocument();
    expect(screen.getByText(/50%/)).toBeInTheDocument();
    expect(screen.getByText(/2400/)).toBeInTheDocument();
  });
  it('attendance_ratio > 1 按 100% 显示', () => {
    render(<StipendBreakdown record={{ ...fixture, attendance_ratio: '1.50' }} />);
    expect(screen.getByText(/100%/)).toBeInTheDocument();
  });
});
```

**Step 2: 实现**

```jsx
// StipendBreakdown.jsx
import { Descriptions, Statistic } from 'antd';

/**
 * 补助明细展示
 * @param {{ record: StipendRecord }} props
 */
export default function StipendBreakdown({ record }) {
  const ratioNum = Math.min(parseFloat(record.attendance_ratio), 1.0);
  return (
    <div>
      <Statistic
        title="最终补助金额"
        value={parseFloat(record.final_amount)}
        precision={2}
        suffix="元"
        valueStyle={{ color: '#3f8600' }}
      />
      <Descriptions column={1} size="small" style={{ marginTop: 16 }}>
        <Descriptions.Item label="联培生类型">
          {record.student_type === 'master' ? '硕士' : '博士'}
        </Descriptions.Item>
        <Descriptions.Item label="档次">
          {record.grade === 'A' ? 'A 档' : 'B 档'}
        </Descriptions.Item>
        <Descriptions.Item label="基本额度">
          {parseFloat(record.base_amount).toFixed(2)} 元
        </Descriptions.Item>
        <Descriptions.Item label="档次系数">
          {parseFloat(record.grade_coefficient).toFixed(2)}
        </Descriptions.Item>
        <Descriptions.Item label="出勤比">
          {(ratioNum * 100).toFixed(0)}%
        </Descriptions.Item>
      </Descriptions>
    </div>
  );
}
```

**Step 3: 跑测试 + Commit**

```bash
npm test -- --testPathPattern=components/StipendBreakdown
git add src/features/joint-students/components/StipendBreakdown.jsx src/features/joint-students/components/StipendBreakdown.test.jsx
git commit -m "feat(joint-students): StipendBreakdown 补助明细组件"
```

---

### Phase 3 — 9 个页面(按角色分 4 批)

#### Task 11: 管理员 — StudentListPage(F9)

**Files:**
- Create: `omni_desk_frontend/src/features/joint-students/pages/admin/StudentListPage.jsx`
- Create: `omni_desk_frontend/src/features/joint-students/pages/admin/StudentListPage.test.jsx`

**Step 1: 写测试**

```jsx
// StudentListPage.test.jsx
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import StudentListPage from './StudentListPage';
import * as api from '../../api/students';

jest.mock('../../api/students');

describe('StudentListPage', () => {
  const wrapper = ({ children }) => (
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  );

  it('调用 listStudents 渲染列表', async () => {
    api.listStudents.mockResolvedValue({
      data: { results: [{ id: 1, student_id: '2026001', student_type: 'master' }] },
    });
    render(<StudentListPage />, { wrapper });
    await waitFor(() => expect(screen.getByText('2026001')).toBeInTheDocument());
  });
});
```

**Step 2: 实现**

```jsx
// StudentListPage.jsx
import { Table, Tag, Button, Space } from 'antd';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { listStudents } from '../../api/students';

export default function StudentListPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['joint-students', 'list'],
    queryFn: () => listStudents(),
  });
  const rows = data?.data?.results ?? [];

  const columns = [
    { title: '学号', dataIndex: 'student_id' },
    { title: '姓名', dataIndex: ['personnel', 'name'] },
    {
      title: '类型',
      dataIndex: 'student_type',
      render: (t) => (t === 'master' ? <Tag color="blue">硕士</Tag> : <Tag color="purple">博士</Tag>),
    },
    {
      title: '状态',
      dataIndex: 'is_active',
      render: (a) => (a ? <Tag color="green">在读</Tag> : <Tag>已毕业</Tag>),
    },
    {
      title: '操作',
      render: (_, r) => (
        <Space>
          <Link to={`/joint-students/admin/students/${r.id}`}>查看</Link>
          <Link to={`/joint-students/admin/students/${r.id}/edit`}>编辑</Link>
        </Space>
      ),
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <Space style={{ marginBottom: 16 }}>
        <Link to="/joint-students/admin/students/new">
          <Button type="primary">新建联培生</Button>
        </Link>
      </Space>
      <Table rowKey="id" loading={isLoading} dataSource={rows} columns={columns} />
    </div>
  );
}
```

**Step 3: 跑测试 + Commit**

```bash
npm test -- --testPathPattern=admin/StudentListPage
git add src/features/joint-students/pages/admin/StudentListPage.jsx src/features/joint-students/pages/admin/StudentListPage.test.jsx
git commit -m "feat(joint-students): StudentListPage 列表 + 筛选"
```

---

#### Task 12-13: 管理员 — StudentEditPage(F10) + ReportReviewPage(F11)

**Files:**
- Task 12 → `pages/admin/StudentEditPage.jsx` + `.test.jsx`
- Task 13 → `pages/admin/ReportReviewPage.jsx` + `.test.jsx`

**StudentEditPage 模式**:
- 路径:`/joint-students/admin/students/new` 和 `/students/:id/edit`
- `useParams()` 拿 id,`useQuery` 加载(`getStudent`),`useMutation` 保存(`createStudent` / `updateStudent`)
- Form:学号 / 联培生类型 / 入学日期 / 毕业日期 / 导师(user_account 选择) / 关联 personnel_id
- 毕业后自动 `is_active=false`,毕业日期必填

**ReportReviewPage 模式**:
- 列表展示所有 submitted 状态的报告
- 表格列:联培生 / 年月 / 提交时间 / 出勤(实/应) / 操作(批准 / 驳回)
- 批准 → `approveReport(id)`,驳回 → `rejectReport(id, comment)` 用 `Modal` 收集 comment
- 状态机:仅 `submitted` 可操作

**步骤** = 测试 → 实现 → `npm test -- --testPathPattern=...` → commit

---

#### Task 14-15: 管理员 — CycleManagementPage(F12) + StipendReviewPage(F13)

**CycleManagementPage**:
- 列出所有考核批次,按年月倒序
- 列:年月 / 状态(Tag) / 报告截止 / 打分截止 / 触发方式 / 操作
- 操作:无当前批次时显示"手动触发本月批次";status=collecting 时显示"强制截止";status=closed 显示"查看补助"
- 触发:`createCycle` mutation

**StipendReviewPage**:
- 选定一个 cycle,展示 `StipendRecord` 列表
- 列:联培生 / 排名 / 档次(GradeBadge) / 出勤比 / 最终金额 / 状态 / 操作
- 操作:status=pending + 是联培生管理员 → 显示"复核通过并锁定"(`lockStipend(id)`)
- 锁定后:联培生可在自己页面看到

---

#### Task 16: 专家 — ExpertScoringPage(F14)

**Files:**
- Create: `pages/expert/ExpertScoringPage.jsx` + `.test.jsx`

**模式**:
- 当前活跃 cycle 自动加载(`listCycles({ status: 'collecting' })`)
- 已 approved 月度报告 + 当前 cycle 列表展示
- 表格列:联培生 / 工作进展 / 出勤 / 当前分数 / 操作
- 未打分 → "打分"按钮 → `Modal` 收集 score (0-100) + comment → `createScore`
- 已打分 → 显示分数(只显示自己的;**不**显示其他专家分数,符合设计文档权限矩阵)
- 提交后 `is_locked=True`,admin 可解锁

---

#### Task 17: 联培生 — MyReportsPage(F15)

**Files:**
- Create: `pages/student/MyReportsPage.jsx` + `.test.jsx`

**模式**:
- 当前用户关联的联培生 → 加载月度报告
- 列表按月份倒序
- 状态:draft(可编辑+提交) / submitted(等待审核) / approved(只读) / rejected(可改)+ 显示审核意见
- 提交:`submitReport(id)`,驳回重提:用 `updateReport` 修改 → `submitReport`
- 顶部"+ 新建月度报告"按钮(仅当本月不存在已 approved 报告)

---

#### Task 18: 联培生(续) + 导师 — MyStipendsPage(F16) + MentorOverviewPage(F17)

**MyStipendsPage**:
- 等同联培生版的"我的补助"列表
- 仅 `status=locked` 的 `StipendRecord` 显示;`stipendBreakdown` 组件展示明细
- 顶部显示本年度累计(简单 sum)

**MentorOverviewPage**:
- 当前 mentor → 列出名下联培生
- 列:姓名 / 类型 / 本月报告状态 / 本月出勤(若已 approved)
- 仅只读,**不能**评分或审核

---

### Phase 4 — 路由 + 菜单 + 路由测试

#### Task 19: 路由注册(M1 + M2 + F18 路由快照)

**Files:**
- Modify: `src/routes/lazyImports.js`(M1 — 加 9 个 lazy import)
- Modify: `src/routes/index.jsx`(M2 — 加 13 条路由)
- Create: `src/features/joint-students/__tests__/routes.test.jsx`(F18)

**Step 1: 修改 lazyImports.js**

找出 `routes/lazyImports.js`,在 9 个相邻 page 的 import 段后追加:

```javascript
// 联培生管理(9 个页面引出)
export const StudentListPage = lazy(() => import('@features/joint-students/pages/admin/StudentListPage'));
export const StudentEditPage = lazy(() => import('@features/joint-students/pages/admin/StudentEditPage'));
export const ReportReviewPage = lazy(() => import('@features/joint-students/pages/admin/ReportReviewPage'));
export const CycleManagementPage = lazy(() => import('@features/joint-students/pages/admin/CycleManagementPage'));
export const StipendReviewPage = lazy(() => import('@features/joint-students/pages/admin/StipendReviewPage'));
export const ExpertScoringPage = lazy(() => import('@features/joint-students/pages/expert/ExpertScoringPage'));
export const MyReportsPage = lazy(() => import('@features/joint-students/pages/student/MyReportsPage'));
export const MyStipendsPage = lazy(() => import('@features/joint-students/pages/student/MyStipendsPage'));
export const MentorOverviewPage = lazy(() => import('@features/joint-students/pages/mentor/MentorOverviewPage'));
```

**Step 2: 修改 routes/index.jsx**

```javascript
// 联培生管理(13 条路由,角色权限)
const jointStudentsRoutes = [
  { path: '/joint-students/admin/students', element: <StudentListPage />, pageRouteKey: 'joint_students_admin_students' },
  { path: '/joint-students/admin/students/new', element: <StudentEditPage />, pageRouteKey: 'joint_students_admin_student_new' },
  { path: '/joint-students/admin/students/:id', element: <StudentEditPage />, pageRouteKey: 'joint_students_admin_student_detail' },
  { path: '/joint-students/admin/students/:id/edit', element: <StudentEditPage />, pageRouteKey: 'joint_students_admin_student_edit' },
  { path: '/joint-students/admin/reports', element: <ReportReviewPage />, pageRouteKey: 'joint_students_admin_reports' },
  { path: '/joint-students/admin/cycles', element: <CycleManagementPage />, pageRouteKey: 'joint_students_admin_cycles' },
  { path: '/joint-students/admin/cycles/:id', element: <CycleManagementPage />, pageRouteKey: 'joint_students_admin_cycle_detail' },
  { path: '/joint-students/admin/stipends', element: <StipendReviewPage />, pageRouteKey: 'joint_students_admin_stipends' },
  { path: '/joint-students/expert/scoring', element: <ExpertScoringPage />, pageRouteKey: 'joint_students_expert_scoring' },
  { path: '/joint-students/student/reports', element: <MyReportsPage />, pageRouteKey: 'joint_students_student_reports' },
  { path: '/joint-students/student/reports/new', element: <MyReportsPage />, pageRouteKey: 'joint_students_student_report_new' },
  { path: '/joint-students/student/stipends', element: <MyStipendsPage />, pageRouteKey: 'joint_students_student_stipends' },
  { path: '/joint-students/mentor/overview', element: <MentorOverviewPage />, pageRouteKey: 'joint_students_mentor_overview' },
];
```

> **注意**:`pageRouteKey` 必须与 backend migration 0003 数据完全一致(后端 PR #391 已注册这 12 个 PageRoute key);具体接入方式查 `routes/index.jsx` 现有 `protectedRoute` 包装模式,使用 `ProtectedRoute` + `usePageRoutePermission()`。

**Step 3: 写路由 snapshot 测试(F18)**

```jsx
// routes.test.jsx
import * as router from 'react-router-dom';

describe('联培生路由注册', () => {
  it('挂载 13 条 /joint-students/* 路由', () => {
    const list = (router.__routes || []).filter((r) => r.path?.startsWith('/joint-students/'));
    expect(list.length).toBe(13);
  });
});
```

**Step 4: 跑全量 + build 验证**

```bash
npm test                                  # 期望:全绿
npm run lint                              # 期望:0 errors
npm run build                             # 期望:generate-routes 0 errors + vite build 成功
```

**Step 5: Commit**

```bash
git add src/routes/lazyImports.js src/routes/index.jsx src/features/joint-students/__tests__/routes.test.jsx
git commit -m "feat(joint-students): 13 条路由注册 + 路由 snapshot 测试"
```

---

#### Task 20: Sidebar 菜单(M3)

**Files:**
- Modify: `src/shared/components/sidebar/Sidebar.jsx`

**Step 1: 加菜单项**

```jsx
// 在 Sidebar 的 menu 配置中加入(按角色渲染子菜单):
{
  key: 'joint-students',
  icon: <UserOutlined />,
  label: '联培生管理',
  children: isJointStudentsManager ? [
    { key: 'js-students', label: <Link to="/joint-students/admin/students">联培生列表</Link> },
    { key: 'js-reports', label: <Link to="/joint-students/admin/reports">月度报告审核</Link> },
    { key: 'js-cycles', label: <Link to="/joint-students/admin/cycles">考核批次</Link> },
    { key: 'js-stipends', label: <Link to="/joint-students/admin/stipends">补助复核</Link> },
  ] : isExpert ? [
    { key: 'js-scoring', label: <Link to="/joint-students/expert/scoring">专家打分</Link> },
  ] : isJointStudent ? [
    { key: 'js-my-reports', label: <Link to="/joint-students/student/reports">我的月度报告</Link> },
    { key: 'js-my-stipends', label: <Link to="/joint-students/student/stipends">我的补助</Link> },
  ] : isMentor ? [
    { key: 'js-mentor', label: <Link to="/joint-students/mentor/overview">我的联培生</Link> },
  ] : [],
}
```

**Step 2: 用 `useAuth()` 判断角色,具体 group 名查现有实现**

**Step 3: 测试**

```jsx
// Sidebar.test.jsx 加用例:管理员登录后能看到 4 个子菜单
it('联培生管理员看到 4 个联培生子菜单', () => {
  mockUser({ groups: ['联培生管理员'] });
  render(<Sidebar />, { wrapper });
  expect(screen.getByText('联培生列表')).toBeInTheDocument();
  expect(screen.getByText('月度报告审核')).toBeInTheDocument();
  expect(screen.getByText('考核批次')).toBeInTheDocument();
  expect(screen.getByText('补助复核')).toBeInTheDocument();
});
```

**Step 4: 跑测试 + Commit**

```bash
npm test -- --testPathPattern=Sidebar
git add src/shared/components/sidebar/Sidebar.jsx src/shared/components/sidebar/Sidebar.test.js
git commit -m "feat(joint-students): Sidebar 联培生管理菜单(按角色)"
```

---

### Phase 5 — CI 全绿 + PR

#### Task 21: 跑全量 CI / 修复

**Step 1: 跑全量**

```bash
cd omni_desk_frontend
npm run lint
npm run build
npm test -- --coverage
```

**Step 2: 如有 failures,按 frontend-jsx-in-hook-extension / frontend-eslint-jsx-blindspot 记忆中提到的两个陷阱排查**

**Step 3: 修复完成,写 commit**

```bash
git commit -m "fix(joint-students): lint/build/coverage 修复"
```

---

#### Task 22: 推 + 开 PR

**Step 1: 推 feature 分支**

```bash
git push -u origin feat/restore-joint-students-frontend
```

**Step 2: 开 PR**

```bash
gh pr create --title "feat(joint-students): 恢复前端模块(19 文件 + 13 路由 + 菜单)" --body "$(cat <<'EOF'
## 概要

联培生管理模块前端实现,与已完成合并的后端 PR #391 配对:

- 19 个新文件(6 API + 9 页面 + 2 组件 + 1 路由测试 + 1 聚合入口)
- 13 条路由注册(4 角色权限隔离)
- Sidebar 菜单按角色渲染
- 接口与后端设计文档 `docs/superpowers/specs/2026-07-28-联培生管理模块-design.md` 一致

## 角色页面

- 联培生管理员:StudentList / Edit / ReportReview / CycleManagement / StipendReview
- 专家:ExpertScoring(独立打分,互不可见)
- 联培生:MyReports / MyStipends
- 导师:MentorOverview(只读)

## 验证

- [x] npm run lint 0 errors
- [x] npm run build 成功
- [x] npm test --coverage ≥ 80%
- [x] 路由 snapshot 通过
- [x] 与后端 API 联调(本地 dev server)

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

**Step 3: 监控 CI**

```bash
gh pr checks <PR-number> --watch
# 期望:所有 CI jobs pass
```

**失败时**:`gh pr view <PR-number> --log-failed`,再 fix → amend → push。

---

### Phase 6 — 合并 + 文档

#### Task 23: Squash merge + 清理

**Step 1: 用户合并后,本地清理**

```bash
git switch main
git pull --rebase origin main
git branch -d feat/restore-joint-students-frontend
git push origin --delete feat/restore-joint-students-frontend
```

**Step 2: 跑 `docs/technical/37-joint-students-module.md` §前端章节补充(M4)**

打开 `docs/technical/37-joint-students-module.md`,在末尾追加 §前端章节(目录结构 + 13 条路由表 + 4 角色权限矩阵前端映射 + 关键组件说明),写法按 37-joint-students-module.md 既有章节风格一致。

**Step 3: 更新 README.md(M5)**

`docs/technical/README.md` 章节 37 状态从"后端" → "前端 + 后端 / 100% Jest 单测"

**Step 4: 写用户手册(M6 + M7)**

新建 `docs/user-manual/07-joint-students.md`,章节格式参考 `docs/user-manual/README.md` 现有风格:

```markdown
# 联培生管理

## 角色与权限

(联培生管理员 / 考核专家 / 联培生 / 导师 四角色矩阵)

## 联培生管理员操作

1. 创建联培生档案
2. 审核月度报告
3. 触发考核批次
4. 复核并锁定补助

## 联培生操作

1. 提交月度报告
2. 查看我的补助

## 专家操作

1. 给联培生打分

## 导师操作

1. 查看名下联培生月度报告
```

**Step 5: Commit 文档**

```bash
git add docs/technical/37-joint-students-module.md docs/technical/README.md docs/user-manual/07-joint-students.md docs/user-manual/README.md
git commit -m "docs(technical): 联培生模块前端章节 + 用户手册"
```

---

#### Task 24: 删除本 plan 文档

**Step 1: 删除**

```bash
git rm docs/plans/2026-08-20_restore-joint-students-frontend.md
git commit -m "docs(plan): 联培生前端恢复 完成后删除 plan"
```

**Step 2: 推 + 验证**

```bash
git push origin main
git log --oneline -5
# 期望:看到 docs(technical) + docs(plan) 2 个 commit
```

---

## 风险评估

| 风险 | 等级 | 缓解 |
|---|---|---|
| 路由 `pageRouteKey` 与后端 migration 0003 不匹配 | **高** | 实施前 dump 后端 `permissions_pageroute` 表比对 12 个 key 名;不匹配则在 Task 19 之前补一个 migration 同步 |
| Ant Design 5 与 Windows 7 + Chrome 109 兼容 | 低 | 现有 personnel 模块已用 120 imports,复用现有组件(如 Table, Modal, Form);不加新第三方组件 |
| 测试覆盖率不够 80% | 中 | 每个 API 至少 5 个 mock 测试用例,每个页面 1 个 render + 1 个交互 + 1 个错误态 |
| Sidebar 角色判断实现细节 | 中 | 复用现有 `useAuth()` / `useGroups()` 钩子;不重新实现 group 判断 |
| ESLint 盲区(`iframe rule` 不管 .jsx) | 中 | 跑 `npm run lint src/features/joint-students/` 显式路径,**不能**仅 `eslint .` |
| 后端 API 响应字段命名差异(camelCase vs snake_case) | 中 | 后端用 snake_case;前端 API 函数返回的对象字段直接透传,不另做 transform |
| 现有 `routes.json` 自动生成器扫描不到新增文件 | 中 | `generate-routes.js` 用 Babel AST 解析 `src/routes/index.jsx`,直接 import 即可,无需另写扫描 |

## 依赖状态确认(接续 PR #391)

| 依赖 | 状态 |
|---|---|
| 后端 6 模型 + migration 0001-0003 | ✅ PR #391 已合 main |
| 12 个 PageRoute 数据 | ✅ migration 0003 已 seed |
| 2 个 Group(联培生管理员 / 考核专家组) | ✅ migration 0002 已 seed |
| 知识文档(联合培养协议 / 月度报告 / 补助公式) | ✅ docs/technical/37-*.md 已归档 |
| 现有 `routes/index.jsx` + `lazyImports.js` 模板 | ✅ 存在 |
| 现有 `features/personnel/` 模板 | ✅ 存在 |
| 现有 `Sidebar.jsx` 角色渲染模式 | ✅ 存在 |

## 验收标准(Definition of Done)

- [ ] 19 个新文件 + 7 个修改文件全部在 `feat/restore-joint-students-frontend` 上 commit
- [ ] `npm test --coverage` ≥ 80% 行/分支
- [ ] `npm run lint` 0 errors
- [ ] `npm run build` 成功(`generate-routes` + Vite 0 errors)
- [ ] PR CI 9/9 jobs pass
- [ ] Squash merge → main
- [ ] docs/technical/37-*.md §前端章节 + docs/user-manual/07-*.md 已补
- [ ] docs/plans/2026-08-20_restore-joint-students-frontend.md 已删除
- [ ] feat/restore-joint-students-frontend 分支已删除
- [ ] 工作目录 clean

## 估算

- 19 个 Task × 平均 1-2 小时(含测试)
- 路由 + 菜单 + 文档 ≈ 4 小时
- CI 联调 + 修复 ≈ 4 小时
- **合计 ≈ 6-8 天**(1 人周内)
