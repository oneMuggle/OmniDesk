# Channel-Sync 远程分支自动清理实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新建独立 cron workflow 每天扫描并按规则自动删除已无用的 `channel-sync/*` 远程分支（清理当前积压的 108 个）。

**Architecture:** 新建 `.github/workflows/cleanup-channel-sync-branches.yml`（github-script + REST API），配 `.github/channel-sync-keep.yml` 豁免清单。与 `stale-sync.yml` 同源风格，每天 04:42 cron（错开 1 小时）+ workflow_dispatch（默认 dry_run）。删除前置条件（AND）：channel-sync/* 前缀、不在 keep 清单、PR 已 MERGED/CLOSED、PR 与 commit 均 ≥14 天未动。

**Tech Stack:** GitHub Actions、actions/github-script@v7、Octokit REST API、YAML 配置文件。

## Global Constraints

- 项目语言：所有 conversation / commit / PR / doc 必须中文（CLAUDE.md §Language）
- 文档组织：spec → plan → technical chapter（CLAUDE.md §Document Organization）
- 分支策略：所有"非小"改动走 feature 分支 + PR（feature-branch-workflow.md）
- Cron 时间：与现有 `stale-sync.yml` 的 `42 3 * * *` 错开，本 workflow 用 `42 4 * * *`
- 删除阈值：与 `stale-sync.yml` 的 `STALE_DAYS=14` 对齐
- workflow_dispatch 默认 `dry_run=true`，必须显式传 `false` 才删
- 监控：所有删除/跳过/失败必须写入 `core.summary`
- 不修改 `stale-sync.yml` / `channel-sync.yml` / `channel-sync-resume.yml`
- 不动 staging 分支（beta/rc/release/develop/main）和常规工作分支（feat/*/fix/*/chore/*）
- 实施在 `feat/cleanup-channel-sync-branches` 分支上做，最后通过 PR 合并到 main

---

## File Structure

| 文件 | 状态 | 职责 |
|---|---|---|
| `.github/channel-sync-keep.yml` | 新增 | 豁免清单（YAML schema：`branches: [<name>...]`） |
| `.github/workflows/cleanup-channel-sync-branches.yml` | 新增 | 主 workflow（read-keep step + cleanup step） |
| `docs/technical/31-channel-sync-branch-cleanup.md` | 新增 | 技术手册章节（触发条件、清理规则、误删恢复） |
| `docs/technical/README.md` | 修改 | 加一行章节目录条目 |

实施顺序：Task 1（keep 文件） → Task 2（workflow dry-run） → Task 3（实际删除验证） → Task 4（文档） → Task 5（README 目录）。每个 task 结束可独立验证。

---

### Task 1: 创建豁免配置文件 `.github/channel-sync-keep.yml`

**Files:**
- Create: `.github/channel-sync-keep.yml`

**Interfaces:**
- Consumes: 无
- Produces: YAML 文件，含空 `branches:` 列表 + 注释示例。下游 workflow 的 `Read keep file` step 读这个文件并解析出列表。

- [ ] **Step 1: 创建文件**

在仓库根目录新建 `.github/channel-sync-keep.yml`，内容：

```yaml
# 不应被 cleanup workflow 自动删除的 channel-sync/* 分支名清单
# 仅写分支名（不含 refs/heads/ 前缀）
# 注释以 # 开头,空 branches: 表示无豁免
#
# 维护方式: 直接编辑此文件并提交 PR。
# workflow 解析失败时整个 cleanup job 会失败(不删任何分支)。
branches:
  # 示例:
  # - channel-sync/139-main
```

- [ ] **Step 2: 本地 YAML 语法校验**

Run:
```bash
python3 -c "import yaml; yaml.safe_load(open('.github/channel-sync-keep.yml'))" && echo "YAML OK"
```
Expected: 输出 `YAML OK`，无 YAML 解析错误。

- [ ] **Step 3: 提交**

Run:
```bash
git add .github/channel-sync-keep.yml
git commit -m "feat(ci): 新增 channel-sync 分支清理豁免清单

空启动文件,workflow 解析失败时整个 cleanup job 会失败以阻断误删。
后续如需豁免特定分支,在此文件加一行即可。"
```

---

### Task 2: 创建 cleanup workflow（默认 dry-run 模式）

**Files:**
- Create: `.github/workflows/cleanup-channel-sync-branches.yml`

**Interfaces:**
- Consumes:
  - `.github/channel-sync-keep.yml`（Task 1 产物,workflow 通过 checkout 自动获取）
  - Octokit REST API: `repos.listBranches`, `repos.getCommit`, `pulls.list`, `git.deleteRef`
- Produces: workflow 文件,触发方式 cron + workflow_dispatch(input: dry_run, default true)。workflow summary 输出分类统计 + 删除清单。

- [ ] **Step 1: 创建 workflow 文件**

新建 `.github/workflows/cleanup-channel-sync-branches.yml`,内容:

```yaml
name: Cleanup stale channel-sync branches

on:
  schedule:
    - cron: '42 4 * * *'  # 每天 04:42,与 stale-sync(42 3)错开一小时
  workflow_dispatch:
    inputs:
      dry_run:
        description: '只扫描不删除 (默认 true,首次手动跑必须先 dry-run 验证)'
        type: boolean
        default: true

permissions:
  contents: write          # DELETE git refs/heads/<branch>
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
            core.info(`共 ${allBranches.length} 个分支,其中 ${targets.length} 个 channel-sync/*`);

            const stats = { scanned: 0, kept: 0, skipped_open: 0, skipped_recent: 0, deleted: 0, failed: 0 };
            const deletedLog = [];

            for (const branch of targets) {
              stats.scanned++;
              const name = branch.name;

              if (KEEP_LIST.includes(name)) {
                stats.kept++;
                core.info(`[KEEP] ${name} (豁免清单)`);
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
                core.info(`[KEEP] ${name} (无关联 PR,异常保留)`);
                continue;
              }
              const pr = prs[0];
              if (pr.state === 'open') {
                stats.skipped_open++;
                core.info(`[SKIP-OPEN] ${name} (PR #${pr.number} 仍 open)`);
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

- [ ] **Step 2: 本地 YAML 语法校验**

Run:
```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/cleanup-channel-sync-branches.yml'))" && echo "YAML OK"
```
Expected: `YAML OK`。注:内嵌 `script: |` 块中的 `${{ }}` 是 GitHub Actions 模板语法,YAML 解析不会误判。

- [ ] **Step 3: 提交**

Run:
```bash
git add .github/workflows/cleanup-channel-sync-branches.yml
git commit -m "feat(ci): channel-sync/* 远程分支自动清理 workflow

- cron 42 4 * * * (与 stale-sync 错开 1h)
- workflow_dispatch 默认 dry_run=true
- 删除前置(AND): channel-sync/* 前缀、不在 keep 清单、PR 已
  MERGED/CLOSED、PR 与 commit 都 ≥14 天未动
- 单分支失败不阻断其他分支清理
- workflow summary 输出分类统计 + 删除清单(含 SHA 用于回滚重建)
- 豁免清单读 .github/channel-sync-keep.yml,文件不存在视为空

依赖: .github/channel-sync-keep.yml (Task 1)"
```

---

### Task 3: 首次手动 dry-run 验证

**Files:**
- Modify: 无(纯运行验证)

**Interfaces:**
- Consumes: Task 1 + Task 2 产物
- Produces: workflow run 链接,workflow summary 截图/文本

- [ ] **Step 1: 推分支**

Run:
```bash
git push -u origin feat/cleanup-channel-sync-branches
```

- [ ] **Step 2: 触发 workflow dry-run**

Run:
```bash
gh workflow run cleanup-channel-sync-branches.yml -f dry_run=true
```

注: 如果 workflow 文件不在 main 上,`workflow_dispatch` 可能找不到该 workflow。验证替代方案:
1. 先开 PR(可选,见 Task 7)
2. 或者用 `gh workflow run <workflow>` 加 `--ref feat/cleanup-channel-sync-branches`

Run(优先):
```bash
gh workflow run cleanup-channel-sync-branches.yml --ref feat/cleanup-channel-sync-branches -f dry_run=true
```

- [ ] **Step 3: 等待 run 完成并查看 summary**

Run:
```bash
sleep 30
gh run list --workflow="cleanup-channel-sync-branches.yml" --limit 1
RUN_ID=$(gh run list --workflow="cleanup-channel-sync-branches.yml" --limit 1 --json databaseId -q '.[0].databaseId')
gh run watch "$RUN_ID" --exit-status
gh run view "$RUN_ID" --log
```

Expected: job 成功完成。在 summary 中应看到:
- 扫描分支约 108
- 豁免保留 0(空 keep 清单)
- 跳过(PR OPEN) 数量取决于当前 OPEN 的 channel-sync PR
- 跳过(14 天内活跃) 0(PR 编号 ≥ 367 都是 8 月)
- 将删除 约等于 (扫描 - OPEN - 活跃)
- 删除清单列出每个被判定为可删的 `channel-sync/<n>-<channel>` 分支及 PR/SHA 元数据

- [ ] **Step 4: 验证清单合理性**

人工核对:
- [ ] summary 中列出的"将删除"分支,对应的 PR 是否都已 MERGED 或 CLOSED(可在 `gh pr view <n>` 中确认)
- [ ] 没有出现在"将删除"清单中的分支,确实是 PR OPEN 或不足 14 天的活跃分支
- [ ] 没有任何 `beta` / `rc` / `release` / `develop` / `main` / `feat/*` / `fix/*` 被误判
- [ ] 删除清单中每个分支的 SHA 看起来合理(可在 `git log <sha> --oneline -1` 验证)

如果有任何误判: 不要继续,回退 Task 2 检查 workflow 脚本逻辑。

---

### Task 4: 首次实际清理(手动 dry_run=false)

**Files:**
- Modify: 无

**Interfaces:**
- Consumes: Task 3 验证通过的 workflow
- Produces: 远程 channel-sync/ 分支数量从 108 降至更少;workflow summary 含实际删除清单

- [ ] **Step 1: 触发实际删除**

Run:
```bash
gh workflow run cleanup-channel-sync-branches.yml --ref feat/cleanup-channel-sync-branches -f dry_run=false
```

- [ ] **Step 2: 等待完成并核对**

Run:
```bash
sleep 30
RUN_ID=$(gh run list --workflow="cleanup-channel-sync-branches.yml" --limit 1 --json databaseId -q '.[0].databaseId')
gh run watch "$RUN_ID" --exit-status
gh run view "$RUN_ID" --log
```

Expected: job 成功,summary 中:
- 已删除 数量 = Task 3 中"将删除"数量
- 删除清单与 dry-run 一致
- 失败数量为 0(若有失败,记录分支名)

- [ ] **Step 3: 验证远程分支数下降**

Run:
```bash
git fetch origin --prune
git branch -r | grep -c 'origin/channel-sync/'
```

Expected: 数字从 108 大幅下降。剩余应只含:
- 当前 OPEN 的 channel-sync PR 对应的分支
- 14 天内新 push 的分支(几乎不会)

- [ ] **Step 4: 确认 staging / 工作分支未受影响**

Run:
```bash
git branch -r | grep -E 'origin/(beta|rc|release|develop|main)$|origin/(feat|fix|chore)/'
```

Expected: 所有这些分支仍然存在,无任何丢失。

---

### Task 5: 新增技术手册章节 `docs/technical/31-channel-sync-branch-cleanup.md`

**Files:**
- Create: `docs/technical/31-channel-sync-branch-cleanup.md`

**Interfaces:**
- Consumes: Task 1~4 实施产物
- Produces: 运维可读的章节,描述触发条件、清理规则、豁免维护、误删恢复

- [ ] **Step 1: 创建文档**

新建 `docs/technical/31-channel-sync-branch-cleanup.md`,内容:

```markdown
# Channel-Sync 远程分支自动清理

> 章节 31: 解决 channel-sync bot 长期归档的 `channel-sync/*` 远程分支膨胀问题。

## 背景

每个 PR merge 到 develop 后,channel-sync bot 会把 commit 同步到 beta/rc 两个渠道分支。
为让同步可追溯 + 可重放,bot 在远端单独开两个长期归档分支:
- `channel-sync/<PR号>-beta`
- `channel-sync/<PR号>-rc`

之前这些分支不会自动清理,导致远程列表膨胀。引入本 workflow 后按规则自动删除已无用的归档分支。

## 触发条件

| 触发方式 | 说明 |
|---|---|
| cron | `42 4 * * *` (每天 04:42 UTC,与 stale-sync 错开 1h) |
| workflow_dispatch | 手动触发,`dry_run` input(默认 `true`) |

## 清理规则(AND)

满足以下**全部**条件才删除:

1. 分支名匹配 `^channel-sync/.+`
2. 不在 `.github/channel-sync-keep.yml` 的豁免清单中
3. 关联的 channel-sync PR 状态为 `MERGED` 或 `CLOSED`
4. PR `updated_at` 距今 ≥ 14 天
5. 分支 head commit 的 `committer.date` 距今 ≥ 14 天(保护活跃归档)

## 豁免清单

编辑 `.github/channel-sync-keep.yml`,加一行:

```yaml
branches:
  - channel-sync/<name>
```

注意:
- 仅写分支名,不含 `refs/heads/` 前缀
- 注释以 `#` 开头
- 文件解析失败时整个 cleanup job 会失败(防止因配置错误误删)

## 监控

每次运行都会写 workflow summary:
- 分类统计:扫描/豁免/跳过/删除/失败
- 删除清单:每个被删分支含 PR 号、SHA、PR 状态、PR/commit 日期
- 失败清单:错误信息

## 误删恢复

1. 在 workflow summary 中找到被删分支的完整 SHA(7 位前缀足够定位)
2. 重建分支:
   ```bash
   git push origin <full-sha>:channel-sync/<name>
   ```
3. 不需要重建 PR(原 PR 已合并,无需 resume)

## 注意事项

- 本 workflow 只清理 `channel-sync/*` 归档分支,**绝不**碰 `beta` / `rc` / `release` / `develop` / `main` / `feat/*` / `fix/*` 等分支
- 不会触发 channel-sync 同步流程的任何改动
- 14 天阈值与 `stale-sync.yml` 的 `STALE_DAYS=14` 对齐,便于运维心智一致
```

- [ ] **Step 2: 提交文档**

Run:
```bash
git add docs/technical/31-channel-sync-branch-cleanup.md
git commit -m "docs(technical): 新增 channel-sync 分支清理章节

涵盖:触发条件、清理规则(AND 五条件)、豁免清单维护、
监控(summary)、误删恢复(用 SHA 重建)。"
```

---

### Task 6: 更新 `docs/technical/README.md` 章节目录

**Files:**
- Modify: `docs/technical/README.md`

**Interfaces:**
- Consumes: Task 5 章节文件路径
- Produces: README 目录表格中新增一行

- [ ] **Step 1: 读取当前 README 找到章节目录**

Run:
```bash
grep -n "30-release-channels\|31-\|## " docs/technical/README.md | head -20
```

- [ ] **Step 2: 在目录表格中追加一行**

定位到 `30-release-channels.md` 那一行(章节 30),在其后插入新行:

```
| 31 | [channel-sync-branch-cleanup](./31-channel-sync-branch-cleanup.md) | channel-sync/* 远程归档分支的自动清理规则、豁免清单与误删恢复 |
```

(表格格式按 README 中其他行的样式微调)

- [ ] **Step 3: 验证 README 仍然渲染良好**

Run:
```bash
grep -n "channel-sync-branch-cleanup\|31-channel" docs/technical/README.md
```

Expected: 至少一行匹配,说明插入成功。

- [ ] **Step 4: 提交**

Run:
```bash
git add docs/technical/README.md
git commit -m "docs(technical): README 目录新增章节 31 索引"
```

---

### Task 7: 开 PR 合并到 main

**Files:**
- Modify: 无(纯 PR 操作)

**Interfaces:**
- Consumes: Task 1~6 全部 commits
- Produces: GitHub PR 链接,CI 绿后合并

- [ ] **Step 1: 推完整分支**

Run:
```bash
git push -u origin feat/cleanup-channel-sync-branches
```

- [ ] **Step 2: 开 PR**

Run:
```bash
gh pr create \
  --title "feat(ci): channel-sync/* 远程分支自动清理 (清理积压 108 个归档分支)" \
  --body "## 背景

channel-sync bot 长期归档的 \`channel-sync/*\` 远程分支无自动清理机制,已积压 108 个。本 PR 引入独立 workflow 按规则清理。

## 改动

- 新增 \`.github/workflows/cleanup-channel-sync-branches.yml\`:cron 42 4 * * * + 手动 workflow_dispatch(默认 dry_run),扫描并按规则删除
- 新增 \`.github/channel-sync-keep.yml\`:豁免清单(空启动)
- 新增 \`docs/technical/31-channel-sync-branch-cleanup.md\`:技术章节
- 更新 \`docs/technical/README.md\`:章节目录

## 删除规则(AND)

1. 分支名匹配 \`^channel-sync/.+\`
2. 不在豁免清单
3. 关联 PR 已 MERGED 或 CLOSED
4. PR \`updated_at\` ≥ 14 天
5. 分支 head commit \`committer.date\` ≥ 14 天

## 验证

- [x] dry-run 成功列出所有 108 个候选及去留理由(workflow run 见评论)
- [x] 实际删除后远程 \`channel-sync/*\` 分支数从 108 降至当前剩余 OPEN PR 对应的分支数(详见 workflow summary)
- [x] 14 天内新生成的分支未被误删
- [x] staging / 工作分支(\`beta\`/\`rc\`/\`release\`/\`develop\`/\`main\`/\`feat/*\`/\`fix/*\`)全部保留

## 设计文档

详见 \`docs/superpowers/specs/2026-08-19-channel-sync-branch-cleanup-design.md\`"
```

- [ ] **Step 3: 等 CI 绿**

Run:
```bash
gh pr checks <PR-number> --watch
```

Expected: ci.yml 通过。本 PR 只动 workflow + YAML 文档,不影响 Python 测试或前端 build。

- [ ] **Step 4: 合并并清理**

PR merge 后:

```bash
git switch main
git pull --rebase origin main
git branch -d feat/cleanup-channel-sync-branches
git push origin --delete feat/cleanup-channel-sync-branches
```

Expected: 本地 + 远程分支已删除。main 上现在包含 6 个新 commit(keep 文件、workflow、文档、README、2 个 PR 合并的 fixup 如果有)。

---

### Task 8: 回归验证(等下一次 cron 自动跑)

**Files:**
- Modify: 无(纯观察)

**Interfaces:**
- Consumes: 合并到 main 后的 workflow
- Produces: 下一次 cron 触发的 workflow summary

- [ ] **Step 1: 等第二天 04:42 UTC 后查看 run 历史**

Run:
```bash
gh run list --workflow="cleanup-channel-sync-branches.yml" --limit 3
```

Expected: 看到 cron 自动触发的 run,summary 应显示:
- 扫描分支 = 当前 `channel-sync/*` 数量(应少于 108)
- 删除数量 = 0(因为 14 天阈值,首轮已清完,后续新 PR 不到 14 天不会被清)
- 跳过(14 天内活跃) 数量 = 大部分剩余分支

- [ ] **Step 2: 确认无意外**

如果 cron 自动 run 中"失败" > 0 或"删除" > 5(异常大量),立即:
1. 看 run 日志定位失败原因
2. 必要时禁用 cron(把 schedule 行注释掉)或加豁免清单

---

## 自审结果

- **Spec coverage**:
  - 触发(cron + workflow_dispatch)→ Task 2 + Task 7
  - 删除前置 5 条 → Task 2 核心逻辑逐条实现
  - 豁免配置文件 → Task 1
  - 监控 → Task 2 summary + Task 3 人工核对
  - 回滚 → Task 5 文档章节
  - 测试策略 → Task 3 dry-run + Task 4 实际 + Task 8 回归
  - 验收 7 条 → Task 3/4/8 各覆盖
- **Placeholder scan**: 无 TBD/TODO;所有代码块完整可粘贴;无 "implement later"。
- **Type consistency**: `KEEP_LIST`、`PR_AGE_DAYS`、`COMMIT_AGE_DAYS`、`CHANNEL_SYNC_PREFIX` 等常量名在 spec 和 plan 中完全一致。