# CI/CD 六项改进实施计划

> 日期：2026-05-11
> 目标：完善前端镜像、后端镜像、桌面端程序的自动化构建流程

---

## 背景

项目已具备基础CI/CD能力，但存在以下缺口：
- `develop` 分支不会构建Docker镜像，仅做代码检查
- 桌面端Workflow未使用spec文件优化配置
- 后端Dockerfile引用的 `entrypoint.sh` 缺失
- 桌面端无版本化GitHub Release机制
- 桌面端构建后无产物验证
- 桌面端runner `windows-latest` 可能不兼容Win7

---

## 改进项清单

| # | 改进项 | 文件 | 优先级 |
|---|--------|------|--------|
| 1 | 创建 entrypoint.sh | `omni_desk_backend/entrypoint.sh`（新建） | 高 |
| 2 | develop分支构建Docker镜像 | `.github/workflows/build-and-push-images.yml` | 高 |
| 3 | 桌面端使用spec文件打包 | `.github/workflows/desktop_notifier_ci.yml` | 高 |
| 4 | 桌面端Win7兼容runner | `.github/workflows/desktop_notifier_ci.yml` | 中 |
| 5 | 桌面端构建产物验证 | `.github/workflows/desktop_notifier_ci.yml` | 中 |
| 6 | 桌面端版本化GitHub Release | `.github/workflows/desktop_notifier_ci.yml` | 中 |

---

## 实施步骤

### Phase 1：基础修复（步骤1、2可并行）

#### 步骤 1：创建 `omni_desk_backend/entrypoint.sh`

**原因**：Dockerfile 第82-83行引用 `./entrypoint.sh`，第94行作为ENTRYPOINT，但文件不存在。

**文件**：`omni_desk_backend/entrypoint.sh`（新建）

**内容**：

```bash
#!/bin/bash
set -e

echo "Waiting for database..."
until python -c "
import psycopg2
import os
try:
    conn = psycopg2.connect(
        host=os.environ.get('POSTGRES_HOST', 'db'),
        port=os.environ.get('POSTGRES_PORT', '5432'),
        dbname=os.environ.get('POSTGRES_DB', 'omnidesk'),
        user=os.environ.get('POSTGRES_USER', 'omnidesk'),
        password=os.environ.get('POSTGRES_PASSWORD', ''),
        connect_timeout=5
    )
    conn.close()
    print('Database is ready!')
except psycopg2.OperationalError:
    print('Database not ready yet, retrying...')
    exit(1)
"; do
    sleep 2
done

echo "Running database migrations..."
python manage.py migrate --noinput

if [ -n "${COLLECT_STATIC}" ] && [ "${COLLECT_STATIC}" = "true" ]; then
    echo "Collecting static files..."
    python manage.py collectstatic --noinput
fi

echo "Starting application..."
exec "$@"
```

#### 步骤 2：develop分支构建Docker镜像

**文件**：`.github/workflows/build-and-push-images.yml`

**三处改动：**

1. **触发条件增加develop分支**：`push.branches` 和 `pull_request.branches` 增加 `develop`
2. **tag逻辑**：develop分支使用 `develop` 和SHA tag，不使用 `latest`；main分支保留 `latest`
3. **push条件**：允许develop分支推送镜像到GHCR

---

### Phase 2：桌面端CI整合（步骤3、4、5、6串行）

#### 步骤 3：桌面端使用spec文件打包

**文件**：`.github/workflows/desktop_notifier_ci.yml`

**改动**：将 `pyinstaller --onefile --windowed --name OmniDeskNotifier main.py` 替换为 `pyinstaller main.spec`

#### 步骤 4：桌面端Win7兼容runner

**改动**：runner `windows-latest` → `windows-2019`

#### 步骤 5：桌面端构建产物验证

**改动**：在 `upload-artifact` 前添加步骤，验证 `dist/OmniDeskNotifier.exe` 存在

#### 步骤 6：桌面端版本化GitHub Release

**改动**：在main分支推送时，添加 `softprops/action-gh-release@v2` 步骤，从 `deployment/docker/VERSION` 读取版本号创建Release

---

### Phase 3：验证

#### 步骤 7：确认spec文件完整性

**文件**：`desktop_notifier/main.spec`

已确认 `--add-data` 参数（主题文件打包）配置正确，无需修改。

---

## 实施顺序与依赖关系

```
Phase 1（可并行）
├── 步骤 1: 创建 entrypoint.sh ────── 无依赖
└── 步骤 2: 修改 build-and-push-images.yml ── 无依赖

Phase 2（串行，依赖Phase 1）
├── 步骤 3: 桌面端spec文件打包 ──── 无依赖
├── 步骤 4: 桌面端Win7兼容runner ── 无依赖
├── 步骤 5: 桌面端构建产物验证 ──── 依赖步骤3
└── 步骤 6: 桌面端GitHub Release ── 依赖步骤3、4、5

Phase 3
└── 步骤 7: 确认spec文件 ────────── 无依赖
```

---

## 风险评估

| 改进项 | 风险等级 | 风险描述 | 缓解措施 |
|--------|----------|----------|----------|
| develop构建镜像 | 低 | develop分支推送会触发构建 | 使用develop tag，不影响生产 |
| entrypoint.sh | 中 | 数据库连接参数可能不匹配 | 使用环境变量默认值 |
| spec文件替换 | 低 | 命令行与spec有差异 | 已确认datas参数等价 |
| windows-2019 | 低 | 将来可能被GitHub弃用 | 当前仍受支持 |
| 构建验证 | 低 | 验证失败阻断后续 | 这是预期行为 |
| GitHub Release | 中 | 同版本重复推送 | action-gh-release v2支持幂等 |

---

## 成功后验证清单

- [ ] develop分支推送后，GHCR中能看到 `develop` 和SHA标签的后端/前端镜像
- [ ] main分支推送后，`latest` 标签仍然存在
- [ ] entrypoint.sh在本地Docker构建中能正常执行
- [ ] 桌面端CI使用windows-2019 runner成功构建
- [ ] 桌面端CI生成的exe能通过验证步骤
- [ ] main分支推送桌面端后，GitHub Releases出现带版本号的Release
- [ ] Release中包含exe下载附件

---

## 实施进度

- [x] 步骤 1：创建 entrypoint.sh
- [x] 步骤 2：develop分支构建Docker镜像
- [x] 步骤 3：桌面端使用spec文件打包
- [x] 步骤 4：桌面端Win7兼容runner
- [x] 步骤 5：桌面端构建产物验证
- [x] 步骤 6：桌面端版本化GitHub Release
- [x] 步骤 7：确认spec文件完整性
