# 发布渠道机制 — 设计规范

**日期：** 2026-07-06
**项目：** OmniDesk
**作者：** Claude
**状态：** 待用户审阅

---

## 1. 背景与目标

### 1.1 问题

OmniDesk 当前只有一套发布链路：git push 到 main → CI 自动打 `vX.Y.Z` 镜像 tag → `package_offline_bundle.sh` 打 `omnidesk-offline-vX.Y.Z` 离线包 → 运维升级。

存在以下不足：

- **没有预发布机制**：所有变更直接进入 main 即被打上 `vX.Y.Z`，发布前没有"内部测试"和"客户预览"环节
- **没有版本标识渠道**：镜像仓库里 `latest`、`develop`、`sha-<short>`、`v0.5.9` 混在一起，运维无法一眼判断一个 tag 是开发版还是稳定版
- **没有 hotfix 渠道**：stable 版本发布后，紧急修复只能塞进下一个 minor，缺乏明确的"已发布版本的紧急修复"路径
- **版本号携带信息不足**：`v0.5.9` 看不到它是经过 alpha/beta/rc 哪个阶段发布的，也看不到它和前一个 stable 之间经历了几个预发布版

### 1.2 目标

引入 4 段式发布渠道：**alpha / beta / preview (RC) / stable**，外加 **hotfix** 用于 stable 后的紧急修复，让：

1. **开发者**可以在 main 上放心合并，每个 alpha 版自动有镜像可拉
2. **内测组**在 beta 分支拿到稳定的内测包，反馈驱动 minor bump
3. **客户/领导**在 preview 分支拿到预发布的 RC 包做最终验证
4. **生产**永远只装 stable 分支的版本，紧急修复走 hotfix
5. **运维**通过镜像 tag 后缀、目录前缀、BUILD-MANIFEST 的 `channel` 字段一眼区分

### 1.3 非目标

- 不实现自动晋级（alpha → beta → preview → stable 仍需要人工决策 + PR）
- 不实现自动通知/邮件/钉钉机器人
- 不实现多 stable 并行维护（仅维护当前最新 stable，旧 stable 自动归档）
- 不改变现有的 DB 迁移流程（仍走 `check_migrations` + `backup_db` + `migrate`）

---

## 2. 渠道与分支映射

### 2.1 一分支一渠道

| 渠道 | 分支 | 镜像 tag 后缀 | 适用场景 |
|---|---|---|---|
| alpha | `main` | `-alpha.N` | 开发自测，每日构建 |
| beta | `beta` | `-beta.N` | 内测组验证 |
| preview | `rc` | `-rc.N` | release candidate，正式发布前预览 |
| stable | `release` | 无 | 正式生产 |
| hotfix | `release` | 无（PATCH bump） | stable 已发布后的紧急修复 |

### 2.2 分支生命周期

```
main ──┐
       ├── PR 合并 ──→ 生成 alpha 镜像 + 离线包
       │              ↑
       │              开发者自测
       │
       └── promote ──→ 切到 beta 分支（cherry-pick / merge）
                        │
                        └── PR 合并 ──→ 生成 beta 镜像 + 离线包
                                       ↑
                                       内测组测试

beta ──┐
       └── promote ──→ 切到 rc 分支
                        │
                        └── PR 合并 ──→ 生成 rc 镜像 + 离线包
                                       ↑
                                       客户/领导预览

rc ──┐
     └── promote ──→ 切到 release 分支
                      │
                      └── PR 合并 ──→ 生成 stable 镜像 + 离线包（去掉后缀）
                                     ↑
                                     正式上线

release ──┐
          └── hotfix PR ──→ PATCH bump → 同步 cherry-pick 回 main/beta/rc
```

### 2.3 分支保护规则（建议在 GitHub 设置）

- `main` / `beta` / `rc` / `release` 均为受保护分支
- PR 必须通过 CI 才能合并
- `release` 分支额外需要 code owner review（hotfix 例外，标注 URGENT）

---

## 3. 版本号规则（SemVer 2.0 + 渠道后缀）

### 3.1 格式

```
MAJOR.MINOR.PATCH[-CHANNEL.N]
```

严格符合 [Semantic Versioning 2.0.0 §9](https://semver.org/spec/v2.0.0.html#spec-item-9) 预发布标签规范。

### 3.2 渠道后缀规则

| 渠道 | 后缀 | 完整版本示例 | 适用场景 |
|---|---|---|---|
| alpha | `-alpha.N` | `1.2.0-alpha.1` | 开发自测，每日构建 |
| beta | `-beta.N` | `1.2.0-beta.3` | 内测组验证 |
| preview | `-rc.N` | `1.2.0-rc.2` | 正式发布前的预览 |
| stable | 无 | `1.2.0` | 正式生产 |
| hotfix | 无（PATCH bump） | `1.2.1` | stable 已发布后的紧急修复 |

### 3.3 关键约定

**约定 1：MAJOR.MINOR.PATCH 在 4 个预发布渠道之间共享数字，序号段各自从 1 重新开始。**

| 阶段 | 版本号 |
|---|---|
| alpha 首发 | `1.2.0-alpha.1` |
| alpha 第 5 次 | `1.2.0-alpha.5` |
| 升 beta，序号重置 | `1.2.0-beta.1` |
| beta 第 3 次 | `1.2.0-beta.3` |
| 升 preview（rc），序号重置 | `1.2.0-rc.1` |
| preview 第 2 次 | `1.2.0-rc.2` |
| stable 发布，去掉后缀 | `1.2.0` |
| hotfix，PATCH bump | `1.2.1` |

**约定 2：渠道升级时不递增 minor。** 也就是说 alpha→beta→preview→stable 全程 MAJOR.MINOR.PATCH 不变，仅后缀变化。

**约定 3：stable 内 hotfix 仅 bump PATCH。** 不动 minor，新生成的版本不与任何预发布版本混编（`1.2.1` ≠ `1.2.0-rc.1`）。

**约定 4：稳定版回滚只允许在同一 stable 系列内。** `1.2.0` 可回滚到 `1.2.0`，但不允许 `1.2.0` 回滚到 `1.2.0-rc.2`（渠道不匹配）。

---

## 4. 镜像 tag 命名

### 4.1 完整 tag 矩阵

| 触发事件 | 分支 | 渠道 | 推到 GHCR 的 tag |
|---|---|---|---|
| PR（任意分支） | `feat/*` `fix/*` | none | `sha-<short>`（仅用于构建缓存） |
| push | `feat/*` `fix/*` | none | `sha-<short>` + `<VERSION>-canary` |
| push | `main` | alpha | `sha-<short>` + `1.2.0-alpha.5` |
| push | `beta` | beta | `sha-<short>` + `1.2.0-beta.1` |
| push | `rc` | preview | `sha-<short>` + `1.2.0-rc.1` |
| push | `release` | stable | `sha-<short>` + `1.2.0` + `latest` |
| push | `release`（hotfix PR） | stable | `sha-<short>` + `1.2.1` + `latest` |

### 4.2 关键决策

- **`latest` 永远只指向 stable 渠道**：避免内测镜像被误标 latest
- **`develop` tag 取消**：原 develop 分支已归入 `main` 的 alpha 渠道
- **`<VERSION>-canary`** 取代原 `develop` tag，用于 feat/fix 分支的临时可拉镜像
- **PR 不打渠道 tag**：节省 GHCR 存储，`sha-<short>` 仅用于 docker buildx 缓存复用

### 4.3 GHCR 镜像列表（命名空间 `ghcr.io/onemuggle`）

```
omni-desk-backend / omni-desk-frontend
├─ latest                          ← 当前 stable
├─ v1.2.1                          ← 最近 stable / hotfix
├─ v1.2.0                          ← 上一 stable
├─ v1.2.0-rc.2                     ← 最近 preview
├─ v1.2.0-rc.1
├─ v1.2.0-beta.3                   ← 最近 beta
├─ v1.2.0-alpha.5                  ← 最近 alpha
├─ 1.2.0-alpha.5-canary            ← 当前 feat 分支（如果有）
├─ sha-abc1234                     ← 任意 commit 的缓存层
└─ ... (历史镜像保留，不主动清理)
```

---

## 5. 离线包命名与 BUILD-MANIFEST

### 5.1 离线包目录命名

| 渠道 | 离线包目录 | 命名规则 |
|---|---|---|
| alpha | `omnidesk-offline-alpha-v1.2.0-alpha.5/` | `<channel>-v<version>` |
| beta | `omnidesk-offline-beta-v1.2.0-beta.1/` | `<channel>-v<version>` |
| preview | `omnidesk-offline-rc-v1.2.0-rc.1/` | `<channel>-v<version>`（rc 是约定简写） |
| stable | `omnidesk-offline-v1.2.0/` | `v<version>`（与现状一致，向后兼容） |
| hotfix | `omnidesk-offline-hotfix-v1.2.1/` | `hotfix-v<version>` |

**约定**：stable 渠道不加 prefix，与现状一致；其他 3 个预发布渠道加 prefix。

### 5.2 正则校验放宽

`package_offline_bundle.sh` 当前正则：

```bash
^[0-9]+\.[0-9]+\.[0-9]+$
```

改为：

```bash
^[0-9]+\.[0-9]+\.[0-9]+(-(alpha|beta|rc)\.[0-9]+)?$
```

### 5.3 BUILD-MANIFEST.json 扩展

新增 `channel` 字段：

```json
{
  "version": "1.2.0-rc.1",
  "channel": "preview",
  "build_time": "2026-07-10T12:00:00Z",
  "git_sha": "abc1234",
  "images": {
    "backend":  { "name": "...", "digest": "...", "size_bytes": 0 },
    "frontend": { "name": "...", "digest": "...", "size_bytes": 0 }
  },
  "base_images": {
    "postgres": "postgres:14-alpine",
    "redis":    "redis:7-alpine",
    "nginx":    "nginx-stable-alpine"
  }
}
```

`core/version.py` 保持原样（直接返回完整字符串），由调用方决定是否解析后缀。

`/api/system/version/` API 增加 `channel` 字段：

```json
{
  "version": "1.2.0-rc.1",
  "channel": "preview",
  "build_time": "2026-07-10T12:00:00Z",
  "django_version": "4.2.x"
}
```

---

## 6. CI 改造

### 6.1 `build-and-push-images.yml` 改造

在 workflow 顶部新增 channel 推导 step：

```yaml
- name: Detect release channel
  id: channel
  run: |
    case "${GITHUB_REF#refs/heads/}" in
      main)    echo "CHANNEL=alpha"   >> "$GITHUB_OUTPUT" ;;
      beta)    echo "CHANNEL=beta"    >> "$GITHUB_OUTPUT" ;;
      rc)      echo "CHANNEL=preview" >> "$GITHUB_OUTPUT" ;;
      release) echo "CHANNEL=stable"  >> "$GITHUB_OUTPUT" ;;
      *)       echo "CHANNEL=none"    >> "$GITHUB_OUTPUT" ;;
    esac

- name: Read version
  id: read_version
  run: echo "VERSION=$(cat deployment/docker/VERSION | tr -d '[:space:]')" >> "$GITHUB_OUTPUT"

- name: Extract metadata for backend image
  id: meta-backend
  uses: docker/metadata-action@v5
  with:
    images: ghcr.io/onemuggle/omni-desk-backend
    tags: |
      type=sha
      type=raw,value=${{ steps.read_version.outputs.VERSION }},enable=${{ steps.channel.outputs.CHANNEL != 'none' }}
      type=raw,value=${{ steps.read_version.outputs.VERSION }}-canary,enable=${{ steps.channel.outputs.CHANNEL == 'none' && github.event_name == 'push' }}
      type=raw,value=latest,enable=${{ steps.channel.outputs.CHANNEL == 'stable' }}
```

frontend 镜像同理。

### 6.2 CI 触发矩阵

| 分支 | 触发条件 | CI 行为 |
|---|---|---|
| `feat/*` `fix/*` | push + PR | 仅 build（不 push）；缓存到 sha tag |
| `main` | push | build + push alpha 镜像 |
| `beta` | push | build + push beta 镜像 |
| `rc` | push | build + push preview 镜像 |
| `release` | push | build + push stable 镜像（含 latest） |

---

## 7. 部署脚本改造

### 7.1 `upgrade.sh` 改造

- 新增 `--target-channel {alpha,beta,preview,stable,hotfix}` 参数
- **渠道校验**：禁止跳级（alpha→stable 不允许，alpha→beta 可以）
- `compare_major()` 保留为最后一道防线（major 版本变更禁止走 upgrade.sh）
- hotfix 是 release 分支内部 PATCH bump，不需要渠道校验

### 7.2 `rollback.sh` 改造

- 备份目录结构改为按渠道隔离：`backups/<channel>/backup_v<VERSION>_<timestamp>.sql.gz`
  - `backups/stable/backup_v1.2.0_20260712-153000.sql.gz`
  - `backups/preview/backup_v1.2.0-rc.2_20260710-093000.sql.gz`
  - `backups/beta/...`、`backups/alpha/...`
  - **hotfix 备份沿用 `stable/` 目录**（hotfix 属于 release 分支内部修复，渠道语义不变）
- `deploy_offline.sh rollback` 增加渠道选择（默认上次同渠道）

### 7.3 `deploy.sh`（离线包内）改造

- manifest 解析时把 `channel` 写入 `.env.production` 注释，便于运维识别当前渠道
- 启动 banner 增加一行：`渠道: preview (v1.2.0-rc.1)`
- `generate_env()` 已从 BUILD-MANIFEST.json 派生 IMAGE_TAG，核心无需大改

---

## 8. CHANGELOG 模板

### 8.1 格式

```markdown
## [未发布]

## [v1.2.1] - 2026-07-15  ← hotfix (stable)

### 修复
- **部署脚本**: hotfix 修复 xxx (abc1234)

## [v1.2.0] - 2026-07-12  ← stable

### 新增
- feat: xxx (commit)

### 修复
- fix: yyy (commit)

## [v1.2.0-rc.2] - 2026-07-10  ← preview (RC)

### 新增
- ...

## [v1.2.0-rc.1] - 2026-07-08  ← preview (RC)

### 修复
- ...

## [v1.2.0-beta.3] - 2026-07-05  ← beta

## [v1.2.0-beta.1] - 2026-06-28  ← beta

## [v1.2.0-alpha.5] - 2026-06-25  ← alpha
```

### 8.2 排序

按 SemVer 字符串排序（`v1.2.1` > `v1.2.0` > `v1.2.0-rc.2` > `v1.2.0-rc.1` > `v1.2.0-beta.3` > ... > `v1.2.0-alpha.1`）。

`generate_release.py._update_changelog()` 改造点：

- 解析时按 SemVer 字符串排序
- 在每个新条目的版本号后追加渠道标注（中文：`alpha` / `beta` / `preview (RC)` / `stable` / `hotfix (stable)`）
- `[未发布]` 段不再放具体条目，所有变更直接以新条目形式追加

---

## 9. 文档更新清单

| 文件 | 改动 |
|---|---|
| `CLAUDE.md` | "Version Update System" 章节增加发布渠道说明，新增"渠道与分支映射"小节 |
| `docs/technical/30-release-channels.md` | 新增章节，含版本号规则 + 分支策略 + 升级流程图 |
| `docs/user-manual/12-deployment-channels.md` | 新增章节，面向运维说明各渠道镜像怎么拉/怎么升 |
| `docs/technical/README.md` | 章节目录新增 30-release-channels 条目 |
| `docs/user-manual/README.md` | 章节目录新增 12-deployment-channels 条目 |
| `deployment/docker/DEPLOYMENT_GUIDE_DOCKER.md` | 更新 offline bundle 命名约定 + 渠道选择指引 |
| `deployment/docker/CHANGELOG.md` | 增加一段"渠道机制引入"说明（v0.6.0 引入） |

---

## 10. 测试清单

| 测试类型 | 内容 | 位置 |
|---|---|---|
| 单元测试（pytest） | 渠道参数解析、bump 重置、tag 格式、CHANGELOG 排序 | `omni_desk_backend/core/tests/test_generate_release.py` |
| 单元测试（bash） | alpha/beta/rc 后缀解析、目录命名生成 | `deployment/docker/tests/test_deploy_image_tags.sh` |
| 单元测试（pytest） | BUILD-MANIFEST.json channel 字段读写 | `omni_desk_backend/core/tests/test_api.py` |
| CI 集成测试 | 4 个渠道各跑一次 build-and-push，校验生成的镜像 tag | `.github/workflows/build-and-push-images.yml` 新增 `release-channel-matrix` job（在 M3 一并实现，需要 `workflow_dispatch` + 4 个分支并行 fan-out） |
| E2E 测试 | 4 个渠道各打一个离线包，在测试环境跑 `deploy.sh start`，确认 `/api/system/version/` 返回 channel 正确 | 手动 + CI 触发 |

---

## 11. 迁移计划

### 11.1 现有 v0.5.x 兼容

- 现有 `v0.5.x` 系列保持为 **stable 渠道历史**（不变）
- 从 `v0.6.0` 起启用新渠道
- 旧的 `omnidesk-offline-v0.5.x/` 目录命名继续兼容（部署脚本只识别新格式）
- 不需要数据库迁移

### 11.2 启用步骤（4 步）

| 步骤 | 操作 | 验证 |
|---|---|---|
| 1 | 创建 `beta`、`rc`、`release` 三个空分支（从 main HEAD 拉出） | `git branch -a` 可见 |
| 2 | 部署代码改造：合并本 spec 的实现 PR 到 main | CI 全绿 |
| 3 | 创建第一个 alpha 版（`v0.6.0-alpha.1`） | 离线包 alpha 渠道可见 |
| 4 | 演练晋升 alpha → beta → rc → release | 4 个渠道各自有镜像 |

---

## 12. 风险与缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| GHCR 镜像数量激增 | 存储成本上升 | 定期清理 sha-only tag；`ghcr-cleanup.yml` 月度 job 保留近 30 天 |
| 渠道晋升流程漏 cherry-pick | 渠道之间版本错乱 | 在 PR 模板强制填写"晋升自哪个版本/哪个 commit" |
| 运维误装 alpha 到生产 | 生产事故 | `upgrade.sh` 增加渠道白名单：`--target-channel=stable` 时拒绝 alpha/beta/rc 镜像 |
| 旧 deploy.sh 不识别新 channel 字段 | 兼容性问题 | BUILD-MANIFEST.json 缺 channel 时 default 为 `stable`（向后兼容） |
| hotfix 不同步到 main | main 分支 bug 累积 | release 分支 hotfix PR 必须勾选"已 cherry-pick 回 main/beta/rc"复选框 |

---

## 13. 决策记录

- **2026-07-06**：采用方案 A（SemVer 后缀法），舍弃方案 B（tag 前缀法，破坏现有 v 前缀）和方案 C（目录隔离法，版本号重复）
- **2026-07-06**：采用"一分支一渠道"策略（舍弃单分支 + git tag 区分）
- **2026-07-06**：支持 hotfix 独立渠道（4 段 SemVer）
- **2026-07-06**：CHANGELOG 采用单一文件混合渠道（舍弃按渠道分文件）

---

## 附录 A：实施里程碑

| 阶段 | 内容 | 估时 |
|---|---|---|
| M1 | `generate_release.py` 支持 channel 参数 + bump 重置 | 0.5 天 |
| M2 | `core/version.py` 增强 + `/api/system/version/` API 增加 channel | 0.5 天 |
| M3 | CI `build-and-push-images.yml` 改造 + channel 推导 | 0.5 天 |
| M4 | `package_offline_bundle.sh` 目录命名 + 正则放宽 + BUILD-MANIFEST channel 字段 | 0.5 天 |
| M5 | `upgrade.sh` / `rollback.sh` / 离线 `deploy.sh` 渠道感知 | 1 天 |
| M6 | CHANGELOG 模板改造 + 排序 | 0.5 天 |
| M7 | 单元测试 + 集成测试 + E2E | 1 天 |
| M8 | 文档更新（CLAUDE.md + docs/technical/30-release-channels.md + docs/user-manual/12-deployment-channels.md） | 0.5 天 |
| M9 | （可选）GHCR 镜像清理 workflow `ghcr-cleanup.yml`：月度 job 保留近 30 天 sha-* 与最近 10 个渠道 tag | 0.5 天 |
| **合计** | | **5.5 天**（含 M9） |