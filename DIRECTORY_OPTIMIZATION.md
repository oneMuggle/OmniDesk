# 目录结构优化建议

## 当前目录结构 (优化后)

```
/home/fz/project/InsiteWebsite/
├── omni_desk_backend/           # Django 后端 (23 个 app)
├── omni_desk_frontend/         # React 前端
├── deployment/                # 部署脚本和配置
├── scripts/                   # 脚本
├── docs/                      # 文档
├── tech_docs/                 # 技术文档 (与 docs 功能重叠)
├── .cospec/                   # CoSpec 工具配置
├── .github/                   # CI/CD 配置
├── utils/                     # 工具
├── desktop_notifier/          # 独立工具? (非核心)
├── .gitignore
├── .dockerignore
├── .vscode/                  # IDE 配置
├── .roo/                     # Roo 工具配置
├── .trae/                    # Trae 工具配置
└── README.md
```

---

## 问题分析

### 高优先级 (已清理 ✓)

| 位置 | 问题 | 状态 |
|------|------|------|
| 根目录 `node_modules/` | 与 `omni_desk_frontend/node_modules/` 重复 | ✅ 已删除 |
| 根目录 `package.json` | 混淆来源，前端已有独立 package.json | ✅ 已删除 |
| `omni_desk_backend/.idea/` | IDE 特定配置 | ✅ 已删除 |
| `omni_desk_backend/python` | 空文件 | ✅ 已删除 |
| 根目录 `docker/` | 与 deployment 重复 | ✅ 已删除 |
| 根目录 `misc/` | 杂项，无用文件 | ✅ 已删除 |

### 中优先级 (建议合并/简化)

| 位置 | 问题 | 状态 |
|------|------|------|
| `docs/` vs `tech_docs/` vs `.cospec/wiki/` | 功能重复 | ⚠️ 暂不处理 |
| `deployment/` vs `scripts/` | 部署相关配置分散 | ⚠️ 暂不处理 |

### 低优先级 (可选优化)

| 位置 | 问题 | 状态 |
|------|------|------|
| `.roo/`, `.trae/` | 工具配置 | ⚠️ 暂不处理 |
| `.vscode/` | IDE 配置 | ✅ 已加入 .gitignore |

---

## 已执行的优化操作

### 1. 清理根目录冗余文件 (高优先级) ✓

```bash
# 已删除
rm -rf node_modules/
rm -f package.json
rm -f package-lock.json
rm -rf docker/
rm -rf omni_desk_backend/.idea/
rm -f omni_desk_backend/python
rm -rf misc/
```

### 2. 更新 .gitignore ✓

已在 `.gitignore` 中添加：

```
# IDE
.idea/
.vscode/
.roo/
.trae/
*.code-workspace

# OS
.DS_Store
Thumbs.db

# Python
*.egg-info/
venv/
.venv/
*.log
.pytest_cache/
```

---

## 推荐目录结构 (目标)

```
/home/fz/project/InsiteWebsite/
├── .github/                  # CI/CD 配置
├── .gitignore
├── .dockerignore
├── README.md
├── AGENTS.md                 # Agent 指令
│
├── omni_desk_backend/         # 后端主目录
│   ├── manage.py
│   ├── requirements-dev.txt
│   ├── requirements-prod.txt
│   ├── requirements.txt
│   ├── pytest.ini
│   ├── omni_desk_backend/    # Django 项目配置
│   │   ├── settings/
│   │   ├── urls.py
│   │   └── ...
│   ├── personnel/           # 23 个 Django apps
│   ├── events/
│   ├── documents/
│   ├── config/
│   ├── memos/
│   ├── dify_apps/
│   ├── office_assistant/
│   ├── projects/
│   ├── compliance/
│   ├── ragflow_service/
│   ├── meeting_rooms/
│   ├── sensor_management/
│   ├── sensors/
│   ├── communication/
│   ├── news/
│   ├── permissions/
│   ├── users/
│   ├── llm_service/
│   └── [tests]
│
├── omni_desk_frontend/        # 前端主目录
│   ├── package.json
│   ├── .env
│   ├── .eslintrc.json
│   ├── jest.config.js
│   ├── nginx.conf
│   ├── src/
│   │   ├── components/
│   │   ├── features/
│   │   ├── routes/
│   │   ├── shared/
│   │   └── ...
│   ├── public/
│   └── scripts/
│
├── scripts/                  # 构建和部署脚本
│   ├── build.sh
│   ├── deploy.sh
│   ├── build_and_export.sh
│   ├── export_images.sh
│   └── refactor_pages.bat
│
├── deployment/               # Docker 部署配置
│   ├── docker/
│   └── source/
│
├── docs/                   # 统一文档
│   └── wiki/
│
└── utils/                  # 共享工具
    ├── docs/
    └── docker/
```

---

## 实施清单

| 序号 | 操作 | 优先级 | 状态 |
|------|------|--------|------|
| 1 | 删除根目录 `node_modules/` | 🔴 高 | ✅ 已完成 |
| 2 | 删除根目录 `package.json` 和 `package-lock.json` | 🔴 高 | ✅ 已完成 |
| 3 | 删除 `omni_desk_backend/python` 空文件 | 🔴 高 | ✅ 已完成 |
| 4 | 删除 `omni_desk_backend/.idea/` 目录 | 🔴 高 | ✅ 已完成 |
| 5 | 删除根目录 `docker/` | 🔴 高 | ✅ 已完成 |
| 6 | 删除 `misc/` 目录 | 🟡 中 | ✅ 已完成 |
| 7 | 更新 `.gitignore` 排除 IDE 配置 | 🟢 低 | ✅ 已完成 |
| 8 | 合并 `docker/` 到 `scripts/` | 🟡 中 | ⏸️ 暂不处理 |
| 9 | 统一文档目录结构 | 🟡 中 | ⏸️ 暂不处理 |

---

*更新于: 2026-04-20*
*生成于: 2026-04-20*