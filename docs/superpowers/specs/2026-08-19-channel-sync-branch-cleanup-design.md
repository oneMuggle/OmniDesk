# Channel-Sync 远程分支自动清理设计

> 设计稿：解决 channel-sync bot 长期归档的 `channel-sync/*` 远程分支无限膨胀问题（已积压 108 个）。

## 背景与目标

### 现状

- `channel-sync.yml` workflow 为每个 merge 到 develop 的 PR，在远端开两个长期归档分支：`channel-sync/<PR号>-beta` 和 `channel-sync/<PR号>-rc`。
- 用途：把每次同步的 commit 永久写进去，作为同步快照留底，方便回溯和 resume。
- 现状：远程仓库已积累 108 个 `channel-sync/*` 分支，且**没有任何自动清理机制**。
  - PR 关闭时 bot 用 `git push --force-with-lease` 推独立分支，与 PR 生命周期解耦，关闭 PR 不会触发分支删除。
  - `stale-sync.yml` 只关 PR，不动分支。
  - release 阶段晋升（alpha→beta→rc→stable）也无批量清理逻辑。
- 后果：
  - 远程分支列表膨胀，影响 GitHub UI/CLI 列表加载
  - 没有实际功能用途（半年以上的 PR 极少有人回去查）

### 目标

新增独立 workflow，定期扫描并按规则删除已无用的 `channel-sync/*` 远程分支。**只清理归档分支，不影响 PR、不影响 channel-sync 同步流程本身**。

### 非目标

- 不修改 `channel-sync.yml` / `channel-sync-resume.yml` 的同步逻辑
- 不动 staging 分支（`beta` / `rc` / `release` / `develop` / `main`）
- 不动 `feat/*` / `fix/*` / `chore/*` 等常规工作分支
- 不清理 PR 已 merge 但分支仍有活跃 force-push 的归档分支（保护 resume 场景）

## 设计方案

### 总体策略

**新建独立 workflow `cleanup-channel-sync-branches.yml`，与 PR 状态解耦，每天扫一次远程分支**。

- **触发**：cron `42 4 * * *`（每天 04:42，与 `stale-sync.yml` 的 `42 3` 错开一小时，避免同期争抢 runner）
- **支持手动触发**：`workflow_dispatch`，含 `dry_run` input（默认 `true`，首次手动跑必须先干跑确认）
- **删除前置条件（AND）**：
  1. 分支名匹配 `channel-sync/*`（前缀过滤，匹配 `^channel-sync/.+`）
  2. 不在豁免配置文件 `.github/channel-sync-keep.yml` 的清单中
  3. 关联的 channel-sync PR 状态为 `MERGED` 或 `CLOSED`（非 OPEN）
  4. PR `updated_at` 距今 ≥ 14 天
  5. 分支 head commit 的 `committer.date` 距今 ≥ 14 天（保护正在 force-push 的活跃归档）
- **保留期**：与 `stale-sync.yml` 的 `STALE_DAYS=14` 对齐，便于运维心智一致
- **存量处理**：108 个历史分支按 14 天阈值照常走；2026-07 之前的早已超过 14 天，首轮会大批量清理（这是预期行为）
- **监控**：workflow summary 输出扫描 / 跳过 / 删除 / 失败分类清单
- **回滚**：被删分支的 commit SHA 在 summary 中保留，可 `git push origin <sha>:channel-sync/<name>` 重建

### 组件

#### 新增文件

| 文件 | 作用 |
|---|---|
| `.github/workflows/cleanup-channel-sync-branches.yml` | 主 workflow |
| `.github/channel-sync-keep.yml` | 豁免清单（空启动） |

#### 修改文件

无（`stale-sync.yml` 不动，`channel-sync.yml` 不动）。

### workflow 详细结构

```yaml
name: Cleanup stale channel-sync branches

on:
  schedule:
    - cron: '42 4 * * *'  # 每天 04:42,与 stale-sync 错开
  workflow_dispatch:
    inputs:
      dry_run:
        description: '只扫描不删除 (默认 true)'
        type: boolean
        default: true

permissions:
  contents: write          # DELETE git ref
  pull-requests: read

jobs:
  cleanup:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - name: Read keep file
        id: keep
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            const path = '.github/channel-sync-keep.yml';
            try {
              const content = fs.readFileSync(path, 'utf8');
              const matches = content.match(/^\s*-\s*(\S+)\s*$/gm) || [];
              const list = matches.map(m => m.match(/-\s*(\S+)/)[1]);
              core.setOutput('list', JSON.stringify(list));
              core.info(`豁免清单: ${list.length} 项`);
            } catch (e) {
              if (e.code === 'ENOENT') {
                core.setOutput('list', '[]');
                core.info('无豁免文件,使用空清单');
              } else {
                core.setFailed(`豁免文件解析失败: ${e.message}`);
                return;
              }
            }

      - name: Cleanup
        uses: actions/github-script@v7
        with:
          script: |
            // ... 见下方"核心逻辑"
```

### 核心逻辑（github-script 内嵌）

```javascript
const DRY_RUN = ${{ inputs.dry_run || false }};
const PR_AGE_DAYS = 14;
const COMMIT_AGE_DAYS = 14;
const CHANNEL_SYNC_PREFIX = 'channel-sync/';
const KEEP_LIST = JSON.parse('${{ steps.keep.outputs.list }}');

const owner = context.repo.owner;
const repo = context.repo.repo;
const now = Date.now();
const daysSince = (s) => (now - new Date(s).getTime()) / 86400000;

const allBranches = [];
for (let page = 1; page <= 5; page++) {
  const { data } = await github.rest.repos.listBranches({
    owner, repo, per_page: 100, page,
  });
  allBranches.push(...data);
  if (data.length < 100) break;
}

const targets = allBranches.filter(b => b.name.startsWith(CHANNEL_SYNC_PREFIX));

const stats = { scanned: 0, kept: 0, skipped_open: 0, skipped_recent: 0, deleted: 0, failed: 0 };
const deletedLog = [];

for (const branch of targets) {
  stats.scanned++;
  const name = branch.name;

  if (KEEP_LIST.includes(name)) {
    stats.kept++;
    core.info(`[KEEP] ${name} (豁免)`);
    continue;
  }

  let commitDate;
  try {
    const { data: commit } = await github.rest.repos.getCommit({
      owner, repo, ref: branch.commit.sha,
    });
    commitDate = commit.commit.committer.date;
  } catch (e) {
    stats.failed++;
    core.warning(`[FAIL] ${name} getCommit 失败: ${e.message}`);
    continue;
  }

  if (daysSince(commitDate) < COMMIT_AGE_DAYS) {
    stats.skipped_recent++;
    core.info(`[SKIP-RECENT] ${name} (commit ${Math.floor(daysSince(commitDate))} 天前)`);
    continue;
  }

  const { data: prs } = await github.rest.pulls.list({
    owner, repo, head: name, state: 'all', per_page: 1,
  });
  if (prs.length === 0) {
    stats.kept++;
    core.info(`[KEEP] ${name} (无关联 PR)`);
    continue;
  }
  const pr = prs[0];
  if (pr.state === 'open') {
    stats.skipped_open++;
    core.info(`[SKIP-OPEN] ${name} (PR #${pr.number} still open)`);
    continue;
  }
  if (daysSince(pr.updated_at) < PR_AGE_DAYS) {
    stats.skipped_recent++;
    core.info(`[SKIP-RECENT] ${name} (PR ${Math.floor(daysSince(pr.updated_at))} 天前更新)`);
    continue;
  }

  const logEntry = `${name}  pr=#${pr.number} state=${pr.state} sha=${branch.commit.sha.slice(0,7)} pr_updated=${pr.updated_at.slice(0,10)} commit_date=${commitDate.slice(0,10)}`;

  if (DRY_RUN) {
    stats.deleted++;
    core.info(`[DRY-RUN-DEL] ${logEntry}`);
    deletedLog.push(logEntry);
    continue;
  }

  try {
    await github.rest.git.deleteRef({
      owner, repo, ref: `heads/${name}`,
    });
    stats.deleted++;
    deletedLog.push(logEntry);
    core.info(`[DEL] ${logEntry}`);
  } catch (e) {
    stats.failed++;
    core.warning(`[FAIL-DEL] ${name}: ${e.message}`);
  }
}

const summary = [
  `## Channel-Sync 分支清理${DRY_RUN ? ' (DRY RUN)' : ''}`,
  '',
  `| 指标 | 数量 |`,
  `| --- | --- |`,
  `| 扫描分支 | ${stats.scanned} |`,
  `| 豁免保留 | ${stats.kept} |`,
  `| 跳过(PR OPEN) | ${stats.skipped_open} |`,
  `| 跳过(14 天内活跃) | ${stats.skipped_recent} |`,
  `| ${DRY_RUN ? '将删除' : '已删除'} | ${stats.deleted} |`,
  `| 失败 | ${stats.failed} |`,
  '',
  deletedLog.length ? '### 删除清单\n\n```\n' + deletedLog.join('\n') + '\n```' : '### 无删除项',
].join('\n');
await core.summary.addRaw(summary).write();
```

### 豁免配置文件 `.github/channel-sync-keep.yml`

```yaml
# 不应被 cleanup workflow 自动删除的 channel-sync/* 分支名清单
# 仅写分支名（不含 refs/heads/ 前缀）
# 注释以 # 开头,空 branches: 表示无豁免
branches:
  # 示例:
  # - channel-sync/139-main
```

### 文档

**新增章节**：`docs/technical/3X-channel-sync-branch-cleanup.md`（沿用现有编号体系），包含：
- 触发条件与清理规则
- 豁免清单维护说明
- 误删恢复步骤

更新 `docs/technical/README.md` 章节目录（加一行简介）。

不动 `.github/CHANNEL_SYNC_SETUP.md`（那是 token 配置文档，不属于清理职责）。

## 数据流

```
cron 04:42 UTC → workflow trigger
  ↓
checkout + 读 keep 文件
  ↓
github-script 主体
  ├─ listBranches 分页拉全部分支(100/页,5 页 = 500)
  ├─ client 侧过滤 channel-sync/*
  ├─ 对每个目标:
    ├─ KEEP 列表命中? → 跳过
    ├─ getCommit(head_sha) → 取 commit_date
    ├─ commit_date < 14 天? → 跳过(保护活跃)
    ├─ pulls.list(head=branch, state=all) → 取 PR
    ├─ 无 PR? → 保留(异常)
    ├─ PR 仍 OPEN? → 跳过
    ├─ PR updated_at < 14 天? → 跳过
    └─ deleteRef(heads/branch) → 删除
  └─ 输出 summary
```

## API 调用量估算

- 108 分支 × `getCommit` = 108 次
- 108 分支 × `pulls.list` = 108 次（每次返回 ≤1 条，开销小）
- 0~N 次 `deleteRef`
- 总计 ≤ 220 次读 + ≤ 5 次写

GitHub REST 限制 5000/h/用户身份（workflow 用 `GITHUB_TOKEN`，与 PR/分支操作同身份），远低于上限。

## 错误处理

| 场景 | 行为 |
|---|---|
| 豁免文件不存在 | 视为空清单（不阻断） |
| 豁免文件解析失败 | job 失败，不删任何分支 |
| `getCommit` 失败（404 等） | 跳过该分支，记入 `failed` |
| `pulls.list` 返回空 | 视为"无关联 PR"，跳过（保留） |
| `deleteRef` 返回 403/422（受保护） | 跳过，记入 `failed`，不阻断其他 |
| `deleteRef` 返回 5xx | 抛出失败，整个 job 红（已删的不可回滚，靠 SHA 重建） |
| 单分支处理异常 | 用 try/catch 包住整个迭代体，单个失败不影响其他分支 |

## 测试策略

1. **首次手动跑 dry-run**：
   ```bash
   gh workflow run cleanup-channel-sync-branches.yml -f dry_run=true
   ```
   打开 Actions 页面，确认 summary 列出的"将删除"清单符合预期。
2. **手动跑实际删除**（dry_run=false）：
   - 限 1~2 个测试分支（如手动 push 一个临时 `channel-sync/test-cleanup`）
   - 确认 summary 与预期一致
3. **存量首轮**：
   - 第一次自动 cron 触发后，summary 会一次性清理大量历史分支
   - 这就是 14 天阈值的设计意图，不需要额外防御
4. **回归测试**：故意 push 一个新 `channel-sync/<n>-beta`，验证 14 天内不会被误删

## 风险与依赖

| 风险 | 缓解 |
|---|---|
| 误删正在 resume 的活跃归档 | `committer.date < 14 天` 硬约束 |
| bot 重 push 同名分支但 PR 已被关 | 同上，分支 head commit 时间会刷新 |
| API 限流 | 当前 108 分支远低于 5000/h 上限；未来若涨到几千，可加 `core.info` 计数 + 分批 |
| `channel-sync-keep.yml` 配置错误 | 解析失败 job 红，不删任何分支 |
| GitHub REST API 行为变化 | `deleteRef` 接口自 v3 起稳定，向后兼容 |
| resume workflow 引用已删分支 | resume 在 PR 被合并时触发，合并时分支必然存在；合并后才可能被本 workflow 删除 |

## 实施步骤（迁移到 writing-plans 时细化）

1. 创建 `.github/channel-sync-keep.yml`（空 `branches:` 列表）
2. 创建 `.github/workflows/cleanup-channel-sync-branches.yml`
3. 手动 `workflow_dispatch` 跑一次 dry-run，核对 summary
4. 手动跑一次实际删除（小范围确认）
5. 等下一轮 cron 自动触发，看真实效果
6. 加 `docs/technical/3X-channel-sync-branch-cleanup.md` 章节
7. 更新 `docs/technical/README.md` 目录

## 验收标准

- ✅ workflow 文件能 dry-run 成功列出所有 108 个候选及其去留理由
- ✅ 实际删除运行后，对应的 108 个 `channel-sync/*` 分支数量明显下降
- ✅ 14 天内新生成的 `channel-sync/*` 分支不被误删
- ✅ 豁免清单中的分支不被删
- ✅ PR 仍 OPEN 的 `channel-sync/*` 分支不被删
- ✅ workflow summary 含完整删除清单（含 SHA），可一键重建
- ✅ 失败分支不会阻断其他分支的清理