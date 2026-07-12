# 发布渠道修复同步设计（Channel Fix Sync）

## 背景与目标

OmniDesk 从 v0.6.0 起采用 4 段式发布渠道（alpha/beta/preview/stable），
但目前**没有自动机制**把 `beta` 或 `rc` 上合并的 `fix:` / `perf:` / `refactor:` 提交
同步回 `main`（alpha）。结果是：

- 当 `main` 上做下一次 `alpha → beta` 渠道升级（promote）时，遗漏的修复需要人工补齐
- `release` 的 hotfix 已经声明要"同时 cherry-pick 回 main/beta/rc"，但缺乏自动化
- 团队规模小时易遗漏，规模扩张后不可持续

本设计目标：

1. 在 `main` / `beta` / `rc` 三个渠道分支之间，**双向自动同步** `fix:` / `perf:` / `refactor:` 提交
2. 通过**自动创建的同步 PR**实现：人类仍 review & merge，但搜索 + cherry-pick 的机械工作自动化
3. 冲突时转 draft + 上传 patch + @原作者，由人类解决
4. 与现有内网/离线部署约束兼容（纯 GitHub-native，不引入外部服务）

## 涉及的文件与模块

| 类型 | 文件 | 用途 |
|---|---|---|
| 新增 | `.github/workflows/channel-sync.yml` | 主 workflow |
| 新增 | `.github/CHANNEL_SYNC_SETUP.md` | 配置说明（含 token 设置） |
| 新增 | `tests/test_sync_filter.sh` | 单元测试：commit 类型过滤 |
| 新增 | `tests/fixtures/sync_pr_scenarios.json` | 测试用例数据 |
| 修改 | `docs/technical/30-release-channels.md` | 新增"自动同步"章节，更新流程图 |
| 修改 | `docs/technical/README.md` | 章节目录新增条目 |
| 修改 | `.gitignore` | 忽略 `.sync-state/` 本地缓存（如果引入） |
| 配置 | GitHub repo settings | 创建 `CHANNEL_SYNC_TOKEN`（GitHub App 或 PAT） |

## 技术方案

### 1. 触发条件

```yaml
on:
  pull_request:
    types: [closed]
    branches: [main, beta, rc]
```

**关键过滤**：
- `github.event.pull_request.merged == true`
- PR 标题不以 `🔁 [sync]` 开头（防递归）
- PR 作者不是 `github-actions[bot]`

### 2. Commit 类型过滤

在 detect-sync job 中扫描 PR 内的所有 commit subjects：

```
^[a-f0-9]+ (fix|perf|refactor)(\([^)]+\))?!?: 
```

匹配以下则触发同步：
- `fix: xxx`
- `fix(scope): xxx`
- `perf: xxx`
- `refactor: xxx`

不匹配（保持原样，仅走官方 promote 流程）：
- `feat:`、`feat!:`、`docs:`、`test:`、`chore:`、`ci:`、`build:`、`style:`

大小写敏感（匹配 conventional commits 规范）。

### 3. 目标分支决策矩阵

| 源分支 | 同步目标 |
|---|---|
| main | beta, rc |
| beta | main, rc |
| rc | main, beta |

`release` 不参与自动同步，原因：
- stable 渠道对质量要求最高
- 任何对 release 的修改必须走 `hotfix-v*` 流程 + 人工 review
- 这与现有"渠道守卫"和 `release-channel-matrix.yml` 集成测试一致

### 4. Cherry-pick 流程

每个 (source, target) 对触发一个独立的 sync job：

```
1. checkout target 分支（带完整历史，fetch-depth: 0）
2. git log <source-pr-base>..<source-pr-head> --pretty='%H %s' | grep 上述 regex
   → 得到需要 cherry-pick 的 commit SHA 列表
3. 对每个 SHA 执行 git cherry-pick -x <sha>
   - 成功：继续下一个
   - 失败：
       - git cherry-pick --abort
       - git format-patch -1 <sha> --stdout > conflict.patch
       - 标记 CONFLICT_ON=<sha>，后续步骤跳过 push，转 draft PR
4. 全部成功 → git push origin HEAD:channel-sync/<pr-number>-<target>
5. 用 peter-evans/create-pull-request@v6 开 PR
```

### 5. 同步 PR 规范

- **分支名**：`channel-sync/<source-pr-number>-<target>`
- **标题**：`🔁 [sync] #<source-pr-number> → <target>`
- **Body 模板**：
  ```markdown
  🔁 [sync] #<source-pr-number> → <target>

  自动同步 PR（源 PR #<source-pr-number>）

  - 源分支: `<source>`
  - 源作者: @<author>
  - 同步 commits: <sha-list>

  <!-- auto-sync-source: #<source-pr-number> -->
  <!-- auto-sync-target: <target> -->
  ```
- **冲突状态**：draft + body 追加"⚠️ Cherry-pick 冲突"段，附 patch 下载链接
- **Reviewer 指派** (v1):由 `peter-evans/create-pull-request@v6` 默认行为;暂不实现"源 PR 作者 + 活跃 reviewer"自动匹配 (后续可加)

### 6. 循环防护（三层）

1. **PR 标题前缀** `🔁 [sync]` → filter skip
2. **PR body marker** `auto-sync-source: #<num>` → 同步 job 检测到 marker 时 skip
3. **Actor 过滤**：`github-actions[bot]` 提交的 PR 跳过 trigger

### 7. 配置需求

仓库需要 `CHANNEL_SYNC_TOKEN`（推荐 GitHub App，fallback PAT with `repo` scope）：

- 创建/修改 PR
- push 到 `channel-sync/*` 分支
- 读 PR / commit 元数据

token 配置步骤见 `.github/CHANNEL_SYNC_SETUP.md`。

### 8. 错误处理

| 场景 | 检测 | 行为 |
|---|---|---|
| cherry-pick 冲突 | `git cherry-pick` 非 0 + unresolved conflicts | abort + format-patch + draft PR + @原作者 |
| 目标分支不存在 | checkout 失败 | workflow 失败，发系统级错误日志，**不**开 PR |
| Token 权限不足 | push 返回 403 | workflow 失败，发 `CHANNEL_SYNC_TOKEN` 配置错误提示到 workflow summary |
| 同步 PR 已存在 | `gh pr list --head channel-sync/<n>-<t>` 检查到已存在 | 增量更新：cherry-pick 新 commits → force push 同一分支（保留现有 PR 上下文） |
| Beta/Rc 已包含该 commit | `git merge-base --is-ancestor <sha> <target>` | 跳过该 commit |
| `release` 分支被错误触发 | 仅在 main/beta/rc 上有 trigger | 永不发生（trigger filter 已排除） |

### 9. 测试

**单元测试** (`tests/test_sync_filter.sh`)：
- 12 case，覆盖：
  - 类型识别：`fix:` ✓ / `feat:` ✗ / `chore:` ✗ / `fix(x):` ✓ / `Fix:` ✗（大小写）
  - 多 commit PR：含 `feat+fix` 触发；纯 `feat+docs` 不触发
  - BREAKING CHANGE：`fix!:` ✓
  - merge commit subjects（GitHub 默认 merge 格式）✗（不参与过滤）

**集成测试**（用真实 fork 仓库或 `act`）：
- 在每个 channel 分支制造一个 fix: PR
- 验证另外两个 channel 各收到一个 draft/ready sync PR
- 制造冲突 → 验证 draft + patch

**E2E 烟囱测试**（扩展现有 `release-channel-matrix.yml`）：
- 加一个 `dry-run-sync` job：仅打印"如果这个 PR 合并了，会触发哪些 sync"，不做实际 push
- 每周日 02:00 跑一次，验证 detect 逻辑不退化

## 实施步骤（计划阶段细化）

将作为独立 plan 文档在 `docs/superpowers/plans/2026-07-12-channel-fix-sync.md` 输出。

- [ ] 步骤 1：编写 `tests/test_sync_filter.sh` + 用例数据
- [ ] 步骤 2：编写 `.github/workflows/channel-sync.yml`（detect + sync job）
- [ ] 步骤 3：本地用 `act` 或 fork 仓库跑集成测试
- [ ] 步骤 4：更新 `docs/technical/30-release-channels.md` + README 章节索引
- [ ] 步骤 5：配置 GitHub repo 的 `CHANNEL_SYNC_TOKEN`
- [ ] 步骤 6：首次手动触发一次 dry-run（手动 dispatch input）
- [ ] 步骤 7：观察一周，统计 sync PR 数量 / 冲突率
- [ ] 步骤 8：正式启用（去掉 `if: github.event.pull_request.user.login != 'github-actions[bot]'` 调试限制）

## 风险评估与依赖

| 风险 | 影响 | 缓解 |
|---|---|---|
| Token 泄漏 | 高 | 用 GitHub App（短期 token + 最小权限），不要用长期 PAT |
| 误同步 `release` | 高 | trigger filter 仅 main/beta/rc；CI 端再做一次 base branch 断言 |
| 同步 PR 噪音（开发者收到大量通知） | 中 | 默认 1 reviewer (源 PR 作者)；冲突时再加 reviewer |
| 解决冲突时再触发 sync | 中 | sync PR 标题前缀 + body marker 双保险 |
| 内网环境 GitHub Actions 不可用 | 中 | v1 仅 `pull_request` 触发；后续可加 `workflow_dispatch` 手动触发 + CLI fallback (`deployment/docker/sync_channels.sh`,作为可选增强) |
| `beta` 上累积太多 sync PR | 低 | 每周 review 一次；考虑加 `/sync-batched` 合并命令（v2） |

## 依赖

- 现有 GitHub Actions runner 可用（main 分支的 `build-and-push-images.yml` 已在跑）
- 仓库管理员可创建 GitHub App 或 PAT
- 现有 `release-channel-matrix.yml` 集成测试作为 E2E 参考

## 与现有规范的关系

- `docs/technical/30-release-channels.md` → 在"升级流程图"后新增"自动同步机制"章节
- `docs/technical/19-version-management.md` → 不变（VERSION 文件管理仍是手动的）
- `docs/technical/03-cicd-guide.md` → 新增"Channel Sync"小节作为现有 CI 的扩展
- `docs/plans/` → 不放计划（用 `docs/superpowers/plans/`）