# Channel Sync Workflow 冲突解决流程重构设计

## 背景与目标

### 背景

PR #59 (`test: 触发 channel sync workflow`) 首次启用 channel-sync workflow，在 main / beta / rc 三个渠道分支之间双向自动同步 `fix:` / `perf:` / `refactor:` 提交。设计见 `docs/superpowers/specs/2026-07-12-channel-fix-sync-design.md`（位于 origin/main）。

启用以来已发生 4 次 sync PR 触发，其中 **2 次冲突**（PR #68 `fix/upgrade-pillow-12.3.0` 同步到 beta/rc 时）。冲突处理路径当前实现：

```bash
# channel-sync.yml 当前冲突处理
git cherry-pick --abort || true
git format-patch -1 "$SHA" --stdout > conflict.patch
git commit --allow-empty -m "chore(sync): mark conflict on $SHA"
git push origin "HEAD:$BRANCH" --force-with-lease
# 用 peter-evans/create-pull-request 创建 draft PR + 上传 patch artifact
```

### 观察到的不足

1. **诊断信息不足**：人类拿到 draft PR 后只有 `conflict.patch`（cherry-pick 失败的输出），没有：
   - 三方 diff（base ↔ source ↔ target）
   - 冲突文件的最近改动历史
   - 源分支相对 fork 点的完整变更
2. **PR 引导弱**：body 仅追加一行"⚠️ Cherry-pick 冲突"，无解决步骤
3. **无自动 @ 作者**：源 PR 作者是最熟悉代码的人，但需手工 assign
4. **无 label 标识**：`conflicted-sync` label 不存在，无法搜索/筛选冲突 PR
5. **无续跑机制**：人类解决冲突后需手工 cherry-pick 剩余 commits，再手工开 PR
6. **无测试覆盖**：12 case 单测全在 commit 过滤层面，**冲突路径零覆盖**

### 目标

重构 channel-sync workflow 的**冲突路径**（仅此，happy path 不变），实现：

1. 人类决策者拿到 draft PR 时，**拥有完整三方上下文**（诊断信息）
2. PR 自动引导人类**按步骤解决**（模板增强）
3. 自动 assign 源作者 + 应用 `conflicted-sync` label
4. 人类解决冲突并合并后，**自动续 cherry-pick** 剩余 commits（续跑机制）
5. 冲突路径**有完整测试覆盖**（L1 单元 + L2 集成 + L3 E2E 烟囱）

## 设计哲学

延续 PR #59 的核心分工：

- **机器负责**：detect 冲突 + 收集上下文 + 引导人类 + 续跑
- **人类负责**：理解上下文 + 决策 + 编辑代码 + 合并

关键不变量：
- 「**PR 必须被创建**」（诊断信息失败不阻塞）
- 「**workflow 失败必须可见**」（机器不能静默吞错）
- 「**嵌套 ≤ 2 层**」（防止无限循环）

## 涉及的文件与模块

### 修改

| 文件 | 改动类型 | 备注 |
|---|---|---|
| `.github/workflows/channel-sync.yml` | 重构 conflict 路径 | 新增 4 个 step，PR body 模板升级 |
| `.github/workflows/release-channel-matrix.yml` | 扩展 | 新增 `dry-run-sync-conflict` job |
| `.github/CHANNEL_SYNC_SETUP.md` | 补充 | 新增「冲突解决流程」章节 |
| `docs/technical/30-release-channels.md` | 补充 | 「自动同步」章节新增「冲突解决流程」子节 |

### 新增

| 文件 | 用途 |
|---|---|
| `.github/workflows/channel-sync-resume.yml` | 续跑 trigger（监听 conflicted-sync PR merged 事件） |
| `.github/scripts/dry-run-cherry-pick.sh` | L3 E2E 测试脚本 |
| `tests/test_conflict_handler.sh` | L1 单元测试（5 case） |
| `tests/fixtures/conflict_scenarios.json` | L1 测试数据 |
| `tests/integration/test_conflict_resume.sh` | L2 集成测试入口 |

## 技术方案

### 1. 总体架构

```
保留部分（PR #59）：
  - detect-sync job（不变）
  - cherry-pick job 入口与 matrix 展开（不变）
  - 正常路径（无冲突）100% 兼容（不变）
  - 三层循环防护（扩展一层）

重构部分（仅冲突路径）：
  cherry-pick job 内的「冲突路径」从 3 行扩成 ~80 行的「冲突处理块」
```

### 2. 冲突诊断信息（维度 1）

#### 触发条件
`steps.pick.outputs.has_conflict == 'true'`

#### Step A：Compute conflict context
- 提取三方 SHA：
  - `BASE_SHA = git merge-base "$SOURCE_BRANCH" "$TARGET_BRANCH"`
  - `SOURCE_SHA = $CONFLICT_SHA`（cherry-pick 失败的 commit）
  - `TARGET_SHA = HEAD`（cherry-pick 失败时的 target 当前 HEAD）
- 生成三个 patch：
  - `source.patch`（base ↔ source）
  - `target.patch`（base ↔ target）
  - `diverge.patch`（source ↔ target）
- 解析冲突文件清单：
  - `git diff --name-only --diff-filter=U > conflict_files.txt`

#### Step B：Annotate conflict files
对每个冲突文件，列出源/目标分支最近 5 个改动该文件的 commit，输出为 markdown：

```markdown
=== src/foo.py ===
源分支 (main) 最近改动:
- abc1234 fix: ... (alice, 2026-07-10)
- def5678 refactor: ... (bob, 2026-07-08)

目标分支 (HEAD) 最近改动:
- 789abcd feat: ... (carol, 2026-07-12)
```

#### Step C：Upload conflict bundle
artifact 命名：`conflict-${{ matrix.target }}`

| 文件 | 用途 |
|---|---|
| `source.patch` | 源分支相对 base 的 diff |
| `target.patch` | 目标分支相对 base 的 diff |
| `diverge.patch` | 源 vs 目标的直接 diff（突出分歧） |
| `conflict_files.txt` | 冲突文件清单 |
| `file_history.md` | 每个冲突文件的最近改动历史 |

#### 大小保护
- 总大小 > 5MB → 仅上传 `conflict_files.txt` + `file_history.md`
- PR body 标注「Patch 文件过大，请本地 cherry-pick」

#### 失败降级
任一诊断 step 失败 → `::warning::` 日志 + PR body 标注「诊断信息不完整」，不阻塞主流程。

### 3. PR 增强（维度 2：自动 @ 作者 + 标签 + 模板增强）

#### PR body 模板（draft 状态时）

```markdown
🔁 [sync] #<src> → <target>
自动同步 PR（源 PR #<src>）

- 源分支: `<src>`
- 源作者: @<author>  ← 自动 assign
- 同步 commits: `<sha-list>`

<!-- auto-sync-source: #<src> -->
<!-- auto-sync-target: <target> -->

---

## ⚠️ Cherry-pick 冲突

**冲突 commit**: `<CONFLICT_SHA>`
**目标分支**: `<target>`
**冲突文件**: N 个（详见下方 artifacts）

### 快速解决指引

1. **下载** artifact `conflict-<target>` 获取三件套
2. **本地复现**：
   ```bash
   git fetch origin <target>
   git checkout <target>
   git cherry-pick -x <CONFLICT_SHA>
   # 解决冲突后：
   git cherry-pick --continue
   ```
3. **推送并通知**：
   ```bash
   git push origin HEAD:channel-sync/<src>-<target>
   ```
4. **合并此 PR** 即可触发自动续跑（resume workflow 会 cherry-pick 剩余 commits）

### 上下文

<details>
<summary>源/目标最近改动（来自 file_history.md）</summary>

<!-- 由 Annotate conflict files 步骤生成的 markdown 注入此处 -->

</details>
```

#### 自动 @ 源作者
仅冲突时通过 `actions/github-script@v7` 调用 `issues.addAssignees`。

#### 自动 Label
- Label 名：`conflicted-sync`
- 颜色：`d93f0b`
- 描述：`Channel-sync PR with cherry-pick conflict`
- 实现：先 `getLabel`（404 则 `createLabel`），再 `addLabels`
- 仅冲突时应用

### 4. 续跑机制（维度 3）

#### 触发模型
PR merged 事件 + 多重 filter：

```yaml
on:
  pull_request:
    types: [closed]
    branches: [main, beta, rc]

# 触发条件（job if）：
# - merged == true
# - labels contains 'conflicted-sync'
# - title startsWith '🔁 [sync]'
```

#### 为什么不用 comment/label change trigger？
- comment 误触风险高
- 单纯 label change 不一定合并
- **PR merged** 是「已解决」的最准确信号

#### 文件：`.github/workflows/channel-sync-resume.yml`

```yaml
name: Channel Sync Resume

on:
  pull_request:
    types: [closed]
    branches: [main, beta, rc]

permissions:
  contents: read
  pull-requests: read

jobs:
  detect-resume:
    if: |
      github.event.pull_request.merged == true &&
      contains(github.event.pull_request.labels.*.name, 'conflicted-sync') &&
      startsWith(github.event.pull_request.title, '🔁 [sync]')
    runs-on: ubuntu-latest
    outputs:
      should_resume: ${{ steps.parse.outputs.should_resume }}
      source_pr: ${{ steps.parse.outputs.source_pr }}
      target: ${{ steps.parse.outputs.target }}
      remaining_commits: ${{ steps.parse.outputs.remaining_commits }}
    steps:
      - name: Parse sync PR metadata
        id: parse
        run: |
          # 从 body markers 提取 auto-sync-source / auto-sync-target
          SOURCE_PR=$(echo "$PR_BODY" | grep -oP 'auto-sync-source: #\K\d+' || echo "")
          TARGET=$(echo "$PR_BODY" | grep -oP 'auto-sync-target: \K\S+' || echo "")
          # ... (省略详细 bash)
      - name: Compute remaining commits
        # 1. 拉取源 PR commits list
        # 2. 用 git merge-base --is-ancestor 找出 target 还缺哪些
        # 3. 全缺 → should_resume=false
        # 4. 部分缺 → remaining_commits=<list>

  cherry-pick-remaining:
    needs: detect-resume
    if: needs.detect-resume.outputs.should_resume == 'true'
    # 复用 cherry-pick job 核心步骤
    # 差异：
    # - 标题：🔁 [resume] #<src> → <target>
    # - marker: auto-sync-resume: true
    # - 不加 conflicted-sync label
```

#### 防递归（三层 + 一层）

| 层级 | 实现 |
|---|---|
| 标题前缀 `🔁 [sync]` | detect-resume job if 条件 |
| `conflicted-sync` label | 同上 |
| `auto-sync-source` marker | Parse step 解析失败 → safe skip |
| **新增：`auto-sync-resume` marker** | 原 workflow skip 条件扩展，避免 resume PR 触发 detect-sync |

#### 嵌套层数限制
v1 限制 ≤ 2 层（连续 resume 后再冲突）。超出后 workflow 主动失败 + 报错「嵌套过深，请人工处理」。

### 5. 测试覆盖（维度 4）

#### L1 单元测试：`tests/test_conflict_handler.sh`
5 case：

| # | 用例名 | 验证 |
|---|---|---|
| 1 | `parse_sync_markers_valid` | body marker 正确解析 |
| 2 | `parse_sync_markers_missing` | 缺失 marker → should_resume=false |
| 3 | `compute_remaining_commits_all_applied` | 全已合并 → 空 remaining |
| 4 | `compute_remaining_commits_partial` | 部分合并 → 剩余 SHA 列表 |
| 5 | `pr_body_template_conflict` | 渲染冲突 body 模板，含 ⚠️ 段 |

#### L2 集成测试：fork 仓库
- 创建专用 fork：`OmniDesk/channel-sync-test`（私有）
- 复制 workflow 文件 + 预置数据（两个 fix commit + 一个会冲突的依赖）
- 触发：源 PR → 验证冲突 draft + label + assign → 解决 → 合并 → 验证 resume PR 创建

#### L3 E2E 烟囱：release-channel-matrix 扩展
新增 `dry-run-sync-conflict` job：

```yaml
dry-run-sync-conflict:
  runs-on: ubuntu-latest
  steps:
    - name: Setup test repo
      run: |
        mkdir test-repo && cd test-repo
        git init
        # 制造冲突场景的最小 git 仓库
    - name: Run channel-sync cherry-pick dry-run
      run: bash .github/scripts/dry-run-cherry-pick.sh
```

## 错误处理

### 分类与降级策略

| 类别 | 错误 | 检测 | 处理 |
|---|---|---|---|
| cherry-pick | 进程 crash | exit 异常 | CONFLICT_SHA fallback + 报错到 STEP_SUMMARY |
| cherry-pick | `--abort` 失败 | exit 异常 | `git reset --hard HEAD` 兜底 |
| 诊断 | git diff 三方失败 | exit ≠ 0 | `::warning::`，不阻塞 PR 创建 |
| 诊断 | 文件已删 | git log exit ≠ 0 | 跳过该文件，其余继续 |
| 诊断 | artifact > 5MB | size check | 仅上传关键文件，body 标注 |
| PR | create-pull-request 失败 | action exit | workflow 失败 + 完整诊断写入 STEP_SUMMARY |
| PR | assign / label 失败 | API 4xx | `::warning::`，不影响 PR 创建 |
| PR | label 不存在 | getLabel 404 | 先 createLabel 再 addLabels（idempotent） |
| Resume | 源 PR commits API 不可达 | gh api 失败 | workflow 失败 + 日志指引 |
| Resume | merge-base 全 true | 全已合并 | should_resume=false + 关闭 workflow |
| Resume | **嵌套超 2 层** | 计数器 | workflow 主动失败 |
| 全局 | YAML 语法错 | GitHub 解析 | workflow 不启动（需人工修） |
| 全局 | Token 未配置 | 401 | workflow 失败 + 指向 CHANNEL_SYNC_SETUP.md |
| 全局 | 并发冲突 | race | `concurrency` group 配置 |

### 失败传播原则
- 「PR 必须被创建」和「workflow 失败必须可见」是底线
- 其他都是增强，失败时降级为「少一些上下文」而非「完全失败」

### 监控：GITHUB_STEP_SUMMARY
每次 cherry-pick job 末尾写：

```markdown
## Channel Sync Conflict Run Summary

- Trigger PR: #<src>
- Target: <target>
- Conflict SHA: <sha>
- Files in conflict: N
- Bundle size: X.X MB
- Resume nested level: 0/1/2
- Final state: resolved | pending | failed
```

## 数据流与端到端时序

### 端到端时序（冲突 path）

```
源 PR 合并
    │
    ▼
detect-sync (PR #59) ──→ 触发 cherry-pick job
    │
    ▼
cherry-pick 失败
    │
    ├─ abort + format-patch → CONFLICT_SHA
    │
    ▼
Compute conflict context ──→ 三方 patch
    │
    ▼
Annotate conflict files ──→ file_history.md
    │
    ▼
Upload conflict bundle (artifact)
    │
    ▼
Create sync PR (draft) + assign + label
    │
    ▼
══════════════ 人类介入 ══════════════
    │
    ▼
人类本地解决冲突 + push
    │
    ▼
合并 sync PR (merged + conflicted-sync label + 🔁 [sync])
    │
    ▼
channel-sync-resume.yml 触发
    │
    ▼
Parse markers → source_pr + target
    │
    ▼
Compute remaining commits
    │
    ▼
cherry-pick-remaining
    │
    ├─ 成功 → 创建 🔁 [resume] PR (ready)
    └─ 失败 → 再走冲突路径，嵌套 +1
              └─ 嵌套 ≥ 2 → workflow 失败
```

### 数据流（关键变量传递）

```
detect-sync outputs
├── commits [SHA list]
├── source_branch
├── source_author
├── source_pr_number
└── targets [JSON]

cherry-pick job env / outputs
├── CONFLICT_SHA (env) ← 新增
├── TARGET_SHA = HEAD
├── BASE_SHA = merge-base(...) ← 新增
└── has_conflict (output)

conflict bundle (artifact)
├── source.patch
├── target.patch
├── diverge.patch
├── conflict_files.txt
└── file_history.md

sync PR body
├── 头部信息
├── ⚠️ 冲突段
├── 快速解决指引
├── <details> 上下文
└── markers (auto-sync-source/target)

channel-sync-resume.yml
├── source_pr (from marker)
├── target (from marker)
└── remaining_commits (computed)
```

### 关键不变量
1. 冲突 PR 必须创建成功（诊断信息失败不阻塞）
2. diagnostic artifact 必须在 PR 创建前上传
3. resume 必须在 PR 合并后触发
4. 嵌套 ≤ 2 层
5. marker 解析失败 → safe-skip

## 实施步骤

### 5 个独立 PR（可串行合并）

```
PR-A (基础) ──→ PR-B (增强) ──→ PR-C (续跑) ──→ PR-D (测试) ──→ PR-E (文档)
```

#### PR-A：冲突诊断信息（维度 1）
- 改动：`.github/workflows/channel-sync.yml`
- 新增 step：Compute conflict context / Annotate conflict files / Check artifact size
- 重构 step：Upload conflict patch → Upload conflict bundle
- 工作量：1-1.5 天

#### PR-B：PR 模板与自动 @ 作者（维度 2）
- 改动：`.github/workflows/channel-sync.yml` + `.github/CHANNEL_SYNC_SETUP.md`
- 重构 PR body 模板，新增 assign + label step
- 依赖：PR-A
- 工作量：0.5-1 天

#### PR-C：续跑机制（维度 3）
- 新增：`.github/workflows/channel-sync-resume.yml`
- 改动：`.github/workflows/channel-sync.yml`（skip 条件扩展）
- 依赖：PR-B
- 工作量：2-3 天

#### PR-D：测试覆盖（维度 4）
- 新增：tests/test_conflict_handler.sh + conflict_scenarios.json
- 新增：tests/integration/test_conflict_resume.sh
- 改动：release-channel-matrix.yml（新增 dry-run-sync-conflict job）
- 新增：.github/scripts/dry-run-cherry-pick.sh
- 依赖：PR-C
- 工作量：1.5-2 天

#### PR-E：文档同步
- 改动：docs/technical/30-release-channels.md
- 改动：docs/technical/README.md
- 归档：docs/superpowers/specs/2026-07-15-channel-sync-conflict-rewrite-design.md（本文件）
- 依赖：PR-A/B/C/D 全部合并
- 工作量：0.5 天

### 里程碑

| ID | 完成标志 | DoD |
|---|---|---|
| M0 | 设计批准 | ✅ 本 spec 经用户 review + approve |
| M1 | 诊断信息可用 | PR-A 合并 + 真实冲突触发后 artifact 完整 |
| M2 | PR 增强就绪 | PR-B 合并 + 冲突 PR 含完整 body 段 |
| M3 | 续跑闭环 | PR-C 合并 + 集成测试 fork 跑通 |
| M4 | 测试基线 | PR-D 合并 + 单测/集成/E2E 全绿 |
| M5 | 文档完整 | PR-E 合并 + 文档 review 通过 |
| M6 | 发布 | 5 PR 全部合并 + workflow 稳定运行 1 周无错 |

### 总预估工作量
**5.5-8 天**（约 1.5-2 周）

## 风险评估与依赖

### 风险登记

| ID | 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|---|
| R1 | 三方 diff 文件 > 5MB 频繁触发 | 中 | 低 | size check + 降级 |
| R2 | Resume 嵌套超 2 层 | 低 | 中 | 主动失败 + 报错引导 |
| R3 | 测试 fork 仓库维护成本 | 中 | 低 | 自动化 cron + 季度 review |
| R4 | 源 PR 被 force-push / 删除 | 低 | 高 | resume 检测后报错 + 指引 |
| R5 | GitHub API 限流 | 低 | 中 | retry-with-backoff |
| R6 | conflict label 被管理员重命名 | 低 | 中 | workflow 内 label 创建 idempotent |
| R7 | 任一 PR review 不通过 | 中 | 中 | 每 PR 独立可 revert |

### 依赖
- PR #59 已有 detect-sync 与 cherry-pick job（stable 渠道已运行）
- `secrets.CHANNEL_SYNC_TOKEN` 已配置
- 现有 `release-channel-matrix.yml` 作为 E2E 烟囱参考
- 测试 fork 仓库 `OmniDesk/channel-sync-test` 需创建（运维工作）

## 与现有规范的关系

- `docs/superpowers/specs/2026-07-12-channel-fix-sync-design.md`（origin/main）→ 本设计是其后继
- `docs/technical/30-release-channels.md` → 「自动同步」章节补充「冲突解决流程」子节
- `docs/technical/03-cicd-guide.md` → 不变（channel-sync 是其扩展，不重叠）
- `docs/plans/` → 本设计完成后转入 `docs/plans/2026-07-15_channel-sync-conflict-rewrite.md`（实施计划）

## 边界（不在范围内）

- ❌ 不重构 detect-sync（PR #59 已稳定）
- ❌ 不重构 happy path（100% 兼容）
- ❌ 不引入新 secret（复用 CHANNEL_SYNC_TOKEN）
- ❌ 不引入外部依赖（纯 GitHub-native）
- ❌ 不发 develop/beta/rc（仅 main，避免早期渠道触发）
- ❌ 不实现 reviewer 自动指派算法（v1 简单 assign 源作者足够）
- ❌ 不支持 ≥ 3 层嵌套续跑（YAGNI）