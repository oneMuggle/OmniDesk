# InsiteWebsite 项目夜间实施方案

生成时间：2026-05-03

---

## 一、项目现状总览

### 1.1 Git 状态
- 分支：main（与 origin/main 同步）
- **工作树干净，无待提交变更**

### 1.2 最近提交历史
| 提交 | 内容 |
|------|------|
| 71492f6 | docs: 更新墨染江湖项目夜间实施方案 (2026-04-30) |
| 6226e7c | docs: 添加项目文档和优化报告，更新Docker构建命令 |
| 8c6dbee | refactor(test): 统一测试环境并重构多个组件测试 |
| e179901 | ops(ci): 设置构建产物保留天数为7天 |
| a18018d | ops(部署): 简化docker-compose架构并优化nginx配置 |

### 1.3 技术栈概览
- **后端**：Django 3.2.15 + DRF + PostgreSQL + Redis (Celery) + JWT
- **前端**：React (CRA) + React Router v6 + TanStack Query + Ant Design + MUI
- **架构**：Monorepo（backend + frontend 在同一仓库）

### 1.4 项目结构
```
InsiteWebsite/
├── omni_desk_backend/          # Django 后端
│   ├── omni_desk_backend/       # 主应用
│   │   └── settings/           # 设置模块（base, local, development, production, test）
│   ├── personnel/              # 人员管理
│   ├── events/                 # 事件管理
│   ├── documents/             # 文档管理
│   ├── memos/                  # 备忘录
│   ├── projects/              # 项目管理
│   ├── compliance/            # 合规管理
│   ├── meeting_rooms/        # 会议室管理
│   ├── sensor_management/     # 传感器管理
│   ├── communication/        # 通讯
│   ├── news/                  # 新闻
│   └── ...
├── omni_desk_frontend/         # React 前端
│   ├── src/
│   │   ├── features/          # 22 个功能模块
│   │   ├── routes/            # 路由配置
│   │   ├── components/        # 公共组件
│   │   └── shared/            # 共享资源
│   └── package.json           # CRA + 多 UI 库（AntD + MUI）
├── .github/workflows/          # CI/CD 配置
└── docs/                      # 项目文档
```

---

## 二、CI/CD 现状

### 2.1 工作流配置
| 分支 | 触发 | 执行内容 |
|------|------|----------|
| test | push | pytest 后端 + jest 前端 |
| main | push | Docker 构建 → Windows SSH 部署 |
| develop | push | 分离的后端/前端任务 |

### 2.2 当前 CI 配置（ci-test.yml）
- **后端**：Python 3.11 + pytest + requirements-dev.txt
- **前端**：Node 20 + npm install + jest（`npm test -- --watchAll=false`）
- **缓存**：Pip 和 npm 依赖均有缓存策略

### 2.3 部署配置
- 镜像构建推送到 GHCR
- 通过 SSH 部署到 Windows 服务器（非常规 Django 部署方式）

---

## 三、ESLint 分析

### 3.1 Lint 执行结果
```
npm run lint 执行完成，发现以下问题：
```

| 类型 | 数量 | 说明 |
|------|------|------|
| Warning | 11 | 未使用的 React 导入（常见于测试文件） |
| Error | 8 | EBookManagementPage.test.js 中的直接 Node 访问 |
| Error | 1 | PersonnelEditPage.test.js 中的变量重赋值 |

### 3.2 问题文件清单
**警告（未使用导入）：**
- `AnnouncementsPage.test.js`
- `AuthContext.test.js`
- `Login.test.js`
- `Register.test.js`
- `MemoPage.test.js`
- `DocumentProcessor.js`
- `OfficeAssistant.js`
- `PositionManagementTab.test.js`
- `ProfessionalQualificationTable.test.js`
- `PersonnelDetailPage.test.js`
- `PersonnelEditPage.test.js`

**错误（需要修复）：**
- `EBookManagementPage.test.js` — 违反 testing-library/no-node-access 规则
- `PersonnelEditPage.test.js` — 违反 React 纯度规则（渲染时重赋值变量）

---

## 四、建议优化项

### 4.1 前端 Lint 清理（低优先级）
清理测试文件中未使用的 React 导入，预计改动量小，可批量处理。

### 4.2 测试代码规范修复（中优先级）
- `EBookManagementPage.test.js`：改用 Testing Library 方法访问 DOM
- `PersonnelEditPage.test.js`：将 `formInstance` 变量改为 `useState`

### 4.3 CI/CD 优化（可选）
考虑将 Windows SSH 部署迁移到更标准的 Linux 部署方式，降低维护成本。

### 4.4 依赖管理（低优先级）
项目根目录存在冗余的 `package.json`（含 Vue 依赖），前端有独立的 package.json，建议清理根目录的无用配置。

---

## 五、本轮结论

**InsiteWebsite 工作树干净，无代码变更，无需提交。**

Lint 检查发现 11 处警告和 9 处错误，建议在后续迭代中逐步修复。

---

## 六、后续行动建议

| 优先级 | 事项 | 预计时间 |
|--------|------|----------|
| 低 | 清理测试文件中的未使用 React 导入 | 1 小时 |
| 中 | 修复 EBookManagementPage.test.js 的 DOM 访问方式 | 2 小时 |
| 中 | 修复 PersonnelEditPage.test.js 的变量重赋值问题 | 1 小时 |
| 低 | 清理根目录冗余 package.json | 30 分钟 |

---

*本文件由 Hermes Router Agent 自动生成*