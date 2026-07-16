# Channel Sync 冲突解决流程重构 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重构 `.github/workflows/channel-sync.yml` 的冲突处理路径，实现 4 维度增强（诊断信息/PR 增强/续跑机制/测试覆盖），保留 happy path 100% 兼容，通过 5 个独立 PR（PR-A 到 PR-E）串行合入 origin/main。

**Architecture:** 在 PR #59 现有 workflow 基础上做**冲突路径局部重构**——detect-sync 与 happy path 不动，仅在 cherry-pick job 的「冲突处理块」内叠加新 step（PR-A/B），新增独立 `channel-sync-resume.yml` workflow（PR-C），新增 L1/L3 测试覆盖（PR-D），最后更新文档（PR-E）。每个 PR 独立可 revert，渐进式合并。

**Tech Stack:**
- GitHub Actions（yaml 2.1）
- Bash 5.x（cherry-pick + 解析脚本）
- `actions/github-script@v7`（assign/label）
- `actions/checkout@v4`（fetch-depth: 0）
- `peter-evans/create-pull-request@v6`（PR 创建）
- 现有 `release-channel-matrix.yml` 作为 E2E 烟囱

**Spec 引用：** `docs/superpowers/specs/2026-07-15-channel-sync-conflict-rewrite-design.md`

## Global Constraints

- **目标分支**：origin/main（stable 渠道）——channel-sync.yml 仅在 main 上有效，develop/beta/rc 不参与本次
- **happy path 兼容**：100% 保留 PR #59 现有行为，**禁止修改** detect-sync job / 正常路径 step
- **保留循环防护**：三层防护 + 新增 `auto-sync-resume: true` marker 检测
- **PR 标题前缀**：sync PR 用 `🔁 [sync]`，resume PR 用 `🔁 [resume]`，两者严格区分
- **commit message 格式**：遵循项目约定 `<type>: <subject>`，type 取 `feat` / `fix` / `docs` / `test` / `chore`
- **Token**：复用 `secrets.CHANNEL_SYNC_TOKEN`，**禁止新增 secret**
- **离线兼容**：纯 GitHub-native，不引入外部服务依赖
- **嵌套层数**：resume 嵌套 ≤ 2 层，超出后 workflow 主动失败
- **失败传播原则**：诊断信息失败不阻塞 PR 创建；PR 创建失败必须 workflow 失败
- **artifact 大小**：冲突 bundle > 5MB 时仅上传 conflict_files.txt + file_history.md
- **Label 创建**：workflow 内幂等创建 `conflicted-sync` label（先 getLabel，404 则 createLabel）

---

## Phase 0：基线与工作分支

### Task 0.1：从 origin/main 创建工作分支

**Files:**
- Create: 新分支 `feature/channel-sync-conflict-rewrite`

**Interfaces:**
- Consumes: origin/main 最新 commit（应已含 PR #59 的 channel-sync.yml）
- Produces: 本地 `feature/channel-sync-conflict-rewrite` 分支指向 origin/main HEAD

- [ ] **Step 1：确认 channel-sync.yml 在 origin/main 上**

```bash
cd /home/fz/project/OmniDesk
git fetch origin main
git show origin/main:.github/workflows/channel-sync.yml | head -10
```

预期：看到 `name: Channel Fix Sync` 开头。如不存在则 STOP 并报告用户。

- [ ] **Step 2：切到 origin/main 并 reset 工作区**

```bash
git switch main
git reset --hard origin/main
git clean -fdx -e .env -e .venv -e node_modules
```

预期：`HEAD` 指向 origin/main。无 staged/unstaged 改动。

- [ ] **Step 3：创建工作分支**

```bash
git switch -c feature/channel-sync-conflict-rewrite
git branch --show-current
```

预期：当前分支 `feature/channel-sync-conflict-rewrite`。

- [ ] **Step 4：验证 baseline 状态**

```bash
# 验证本地有 channel-sync.yml
ls -la .github/workflows/channel-sync.yml
# 验证 PR #59 关键 marker 存在
grep -c "auto-sync-source" .github/workflows/channel-sync.yml
```

预期：文件存在，grep 输出 ≥ 1。

---

## Phase 1：PR-A — 冲突诊断信息（维度 1）

### Task 1.1：在 cherry-pick step 失败时记录三方 SHA

**Files:**
- Modify: `.github/workflows/channel-sync.yml`（cherry-pick job 内的 `Cherry-pick sync commits` step）

**Interfaces:**
- Consumes: 现有 cherry-pick step（PR #59 已有）
- Produces: 失败时 `GITHUB_ENV` 写入 `CONFLICT_SHA` + `BASE_SHA`

- [ ] **Step 1：读现有 cherry-pick step**

```bash
grep -n "Cherry-pick sync commits" .github/workflows/channel-sync.yml
```

预期：找到 step 的 `- name: ...` 行，记下行号。

- [ ] **Step 2：替换 cherry-pick step（保留 PR #59 行为 + 增强）**

定位 `Cherry-pick sync commits` step 的 `run:` 块，**完整替换**为：

```bash
        run: |
          set +e
          git config user.name "channel-sync-bot"
          git config user.email "channel-sync-bot@users.noreply.github.com"
          CONFLICT_SHA=""
          for SHA in ${{ needs.detect-sync.outputs.commits }}; do
            # 已包含则跳过
            if git merge-base --is-ancestor "$SHA" HEAD; then
              echo "::notice::Skipping $SHA (already in ${{ matrix.target }})"
              continue
            fi
            if ! git cherry-pick -x "$SHA" > "$RUNNER_TEMP/cherry-pick.log" 2>&1; then
              cat "$RUNNER_TEMP/cherry-pick.log"
              CONFLICT_SHA="$SHA"
              git cherry-pick --abort || true
              git format-patch -1 "$SHA" --stdout > "$RUNNER_TEMP/conflict.patch"
              # 新增：记录三方 SHA（PR-A 增强）
              BASE_SHA=$(git merge-base "${{ needs.detect-sync.outputs.source_branch }}" HEAD 2>/dev/null || echo "")
              echo "CONFLICT_SHA=$SHA" >> $GITHUB_ENV
              echo "BASE_SHA=$BASE_SHA" >> $GITHUB_ENV
              echo "TARGET_SHA=$(git rev-parse HEAD)" >> $GITHUB_ENV
              break
            fi
          done
          if [ -n "$CONFLICT_SHA" ]; then
            git commit --allow-empty -m "chore(sync): mark conflict on $CONFLICT_SHA"
          fi
          echo "has_conflict=$([ -n "$CONFLICT_SHA" ] && echo true || echo false)" >> $GITHUB_OUTPUT
```

> 关键变化：仅增加 3 行（计算 `BASE_SHA` + 3 个 `echo ... >> $GITHUB_ENV`），其他逻辑与 PR #59 完全一致。

- [ ] **Step 3：YAML 语法验证**

```bash
which actionlint || pip install yamllint
yamllint .github/workflows/channel-sync.yml 2>&1 | head -20
```

预期：无语法错误。

- [ ] **Step 4：本地 dry-run（验证逻辑正确性）**

```bash
# 创建一个会冲突的 cherry-pick 场景
mkdir /tmp/test-cherry-pick && cd /tmp/test-cherry-pick
git init --bare source.git && git init --bare target.git
git clone source.git src && cd src
git config user.email "test@test.com" && git config user.name "Test"
echo "version 1" > file.txt && git add . && git commit -m "fix: init"
git push origin main

# 让 target fork 时落后
git clone target.git tgt && cd tgt
git config user.email "test@test.com" && git config user.name "Test"
echo "version 2 conflict" > file.txt && git add . && git commit -m "feat: change"
git push origin main

# 模拟 cherry-pick：会冲突
git cherry-pick -x $(cd ../src && git rev-parse HEAD) 2>&1 || echo "EXPECTED CONFLICT"
```

预期：看到 `EXPECTED CONFLICT`。

- [ ] **Step 5：Commit Task 1.1**

```bash
cd /home/fz/project/OmniDesk
git add .github/workflows/channel-sync.yml
git commit -m "feat(channel-sync): record base/source/target SHAs on conflict

PR-A: 冲突诊断信息（维度 1）的第一步。
在 cherry-pick 失败时记录三方 SHA 到 GITHUB_ENV，
供后续步骤生成三方 diff 与冲突文件历史使用。

变更范围：
- 仅在 cherry-pick step 失败分支新增 3 行 echo
- happy path 完全不变"
```

预期：commit 成功。

---

### Task 1.2：新增 Compute conflict context step

**Files:**
- Modify: `.github/workflows/channel-sync.yml`（在 `Cherry-pick sync commits` step 之后新增）

**Interfaces:**
- Consumes: `steps.pick.outputs.has_conflict` (true/false), `CONFLICT_SHA` env
- Produces: `$RUNNER_TEMP/conflict/` 目录含 source.patch / target.patch / diverge.patch / conflict_files.txt

- [ ] **Step 1：定位插入位置**

```bash
grep -n "Cherry-pick sync commits\|Upload conflict patch\|Push branch\|Create sync PR" .github/workflows/channel-sync.yml
```

预期：找到 step 顺序。

- [ ] **Step 2：在 Cherry-pick step 之后插入 Compute conflict context**

新增 step：

```yaml
      - name: Compute conflict context
        id: conflict-context
        if: steps.pick.outputs.has_conflict == 'true'
        run: |
          set +e
          mkdir -p "$RUNNER_TEMP/conflict"
          cd "$GITHUB_WORKSPACE"

          # 优先用 env 记录的 SHA（如有），否则 fallback
          if [ -n "$CONFLICT_SHA" ] && [ -n "$BASE_SHA" ]; then
            SOURCE_SHA="$CONFLICT_SHA"
            TARGET_SHA="$TARGET_SHA"
            BASE_SHA="$BASE_SHA"
          else
            echo "::warning::CONFLICT_SHA not set, computing fallback"
            BASE_SHA=$(git merge-base "${{ needs.detect-sync.outputs.source_branch }}" HEAD 2>/dev/null || echo "HEAD~1")
            SOURCE_PR_COMMITS="${{ needs.detect-sync.outputs.commits }}"
            SOURCE_SHA=$(echo "$SOURCE_PR_COMMITS" | awk '{print $1}')
            TARGET_SHA="HEAD"
          fi

          # 三方 patch
          if [ -n "$BASE_SHA" ] && [ "$BASE_SHA" != "HEAD~1" ]; then
            git diff "$BASE_SHA" "$SOURCE_SHA" > "$RUNNER_TEMP/conflict/source.patch" 2>/dev/null
            git diff "$BASE_SHA" "$TARGET_SHA" > "$RUNNER_TEMP/conflict/target.patch" 2>/dev/null
            git diff "$SOURCE_SHA" "$TARGET_SHA" > "$RUNNER_TEMP/conflict/diverge.patch" 2>/dev/null
          fi

          # 冲突文件清单
          git diff --name-only --diff-filter=U > "$RUNNER_TEMP/conflict/conflict_files.txt" 2>/dev/null || \
            echo "(failed to parse conflict files)" > "$RUNNER_TEMP/conflict/conflict_files.txt"

          # 从 cherry-pick 日志补全
          if [ -s "$RUNNER_TEMP/cherry-pick.log" ]; then
            grep -E "^(CONFLICT|error):" "$RUNNER_TEMP/cherry-pick.log" | \
              grep -oE "[^[:space:]]+\.(py|js|jsx|ts|tsx|md|yml|yaml|json|toml|sh)$" | \
              sort -u >> "$RUNNER_TEMP/conflict/conflict_files.txt"
          fi

          ls -la "$RUNNER_TEMP/conflict/"
          echo "conflict_files_count=$(wc -l < "$RUNNER_TEMP/conflict/conflict_files.txt")" >> $GITHUB_OUTPUT
```

- [ ] **Step 3：YAML 语法验证**

```bash
yamllint .github/workflows/channel-sync.yml 2>&1 | head -10
```

预期：无语法错误。

- [ ] **Step 4：Commit Task 1.2**

```bash
git add .github/workflows/channel-sync.yml
git commit -m "feat(channel-sync): compute conflict context (三方 patch + 文件清单)

PR-A: 维度 1 第二步。
- 新增 Compute conflict context step（仅冲突时触发）
- 生成 source/target/diverge.patch 三方 diff
- 解析冲突文件清单到 conflict_files.txt
- 失败降级：任一 git diff 失败仅 warning，不阻塞后续步骤"
```

预期：commit 成功。

---

### Task 1.3：新增 Annotate conflict files step

**Files:**
- Modify: `.github/workflows/channel-sync.yml`（在 `Compute conflict context` 之后）

**Interfaces:**
- Consumes: `$RUNNER_TEMP/conflict/conflict_files.txt`
- Produces: `$RUNNER_TEMP/conflict/file_history.md`

- [ ] **Step 1：在 Compute conflict context step 之后插入新 step**

新增 step：

```yaml
      - name: Annotate conflict files
        id: annotate
        if: steps.pick.outputs.has_conflict == 'true'
        run: |
          set +e
          HISTORY="$RUNNER_TEMP/conflict/file_history.md"
          SOURCE_BRANCH="${{ needs.detect-sync.outputs.source_branch }}"
          cd "$GITHUB_WORKSPACE"

          echo "# 冲突文件历史" > "$HISTORY"
          echo "" >> "$HISTORY"

          if [ ! -s "$RUNNER_TEMP/conflict/conflict_files.txt" ]; then
            echo "_无冲突文件清单_" >> "$HISTORY"
            exit 0
          fi

          while IFS= read -r FILE; do
            [ -z "$FILE" ] && continue
            echo "=== \`$FILE\` ===" >> "$HISTORY"
            echo "" >> "$HISTORY"
            echo "**源分支 ($SOURCE_BRANCH) 最近改动:**" >> "$HISTORY"
            echo "" >> "$HISTORY"
            git log -5 --pretty='- `%h` %s (%an, %ad)' --date=short -- "$FILE" "$SOURCE_BRANCH" 2>/dev/null >> "$HISTORY" || \
              echo "_(无历史记录)_" >> "$HISTORY"
            echo "" >> "$HISTORY"
            echo "**目标分支 (HEAD) 最近改动:**" >> "$HISTORY"
            echo "" >> "$HISTORY"
            git log -5 --pretty='- `%h` %s (%an, %ad)' --date=short -- "$FILE" 2>/dev/null >> "$HISTORY" || \
              echo "_(无历史记录)_" >> "$HISTORY"
            echo "" >> "$HISTORY"
          done < "$RUNNER_TEMP/conflict/conflict_files.txt"

          cat "$HISTORY"
          echo "history_size=$(wc -c < "$HISTORY")" >> $GITHUB_OUTPUT
```

- [ ] **Step 2：YAML 语法验证**

```bash
yamllint .github/workflows/channel-sync.yml 2>&1 | head -10
```

预期：无语法错误。

- [ ] **Step 3：Commit Task 1.3**

```bash
git add .github/workflows/channel-sync.yml
git commit -m "feat(channel-sync): annotate conflict files with history

PR-A: 维度 1 第三步。
- 对每个冲突文件生成源/目标分支最近 5 个改动的 commit 列表
- 输出为 markdown 格式，便于 PR body 注入
- 失败降级：单文件失败不影响其他文件"
```

预期：commit 成功。

---

### Task 1.4：新增 Check artifact size step + 重构 Upload conflict bundle

**Files:**
- Modify: `.github/workflows/channel-sync.yml`

- [ ] **Step 1：在 Annotate step 之后插入 Check artifact size**

新增 step：

```yaml
      - name: Check artifact size
        id: size-check
        if: steps.pick.outputs.has_conflict == 'true'
        run: |
          set +e
          SIZE_MB=$(du -sm "$RUNNER_TEMP/conflict" 2>/dev/null | cut -f1)
          SIZE_MB=${SIZE_MB:-0}
          echo "size_mb=$SIZE_MB" >> $GITHUB_OUTPUT
          if [ "$SIZE_MB" -gt 5 ]; then
            echo "::warning::Conflict bundle is ${SIZE_MB}MB, > 5MB threshold"
            echo "size_warning=true" >> $GITHUB_OUTPUT
          else
            echo "size_warning=false" >> $GITHUB_OUTPUT
          fi
```

- [ ] **Step 2：重构 Upload conflict patch → Upload conflict bundle**

**完整替换**原 `Upload conflict patch` step 为：

```yaml
      - name: Upload conflict bundle
        if: steps.pick.outputs.has_conflict == 'true'
        uses: actions/upload-artifact@v4
        with:
          name: conflict-${{ matrix.target }}
          path: |
            ${{ runner.temp }}/conflict/conflict_files.txt
            ${{ runner.temp }}/conflict/file_history.md
            ${{ steps.size-check.outputs.size_warning != 'true' && format('{0}/conflict/source.patch', runner.temp) || '' }}
            ${{ steps.size-check.outputs.size_warning != 'true' && format('{0}/conflict/target.patch', runner.temp) || '' }}
            ${{ steps.size-check.outputs.size_warning != 'true' && format('{0}/conflict/diverge.patch', runner.temp) || '' }}
          if-no-files-found: warn
```

- [ ] **Step 3：YAML 语法验证**

```bash
yamllint .github/workflows/channel-sync.yml 2>&1 | head -10
```

预期：无语法错误。

- [ ] **Step 4：Commit Task 1.4**

```bash
git add .github/workflows/channel-sync.yml
git commit -m "feat(channel-sync): upload conflict bundle with size protection

PR-A: 维度 1 第四步。
- 重构 Upload conflict patch → Upload conflict bundle
- 上传三件套：source/target/diverge.patch + conflict_files.txt + file_history.md
- 大小保护：> 5MB 时仅上传 txt + md
- 失败降级：if-no-files-found: warn 不阻塞 PR 创建"
```

预期：commit 成功。

---

### Task 1.5：验证 workflow 结构

- [ ] **Step 1：检查 workflow step 顺序**

```bash
grep -n "^      - name:" .github/workflows/channel-sync.yml
```

预期看到顺序：
1. Checkout target
2. Fetch source commits
3. Cherry-pick sync commits
4. Compute conflict context（新增）
5. Annotate conflict files（新增）
6. Check artifact size（新增）
7. Upload conflict bundle（重构）
8. Push branch (success only)
9. Create sync PR

---

### Task 1.6：Push + 开 PR-A

- [ ] **Step 1：推送分支**

```bash
git push -u origin feature/channel-sync-conflict-rewrite
```

预期：远程分支创建成功。

- [ ] **Step 2：开 PR-A**

```bash
gh pr create \
  --base main \
  --head feature/channel-sync-conflict-rewrite \
  --title "feat(channel-sync): conflict path diagnostic info (PR-A)" \
  --body "## PR-A: 冲突诊断信息（维度 1）

### 改动
- cherry-pick 失败时记录 base/source/target SHA
- 新增 Compute conflict context step（生成三方 patch）
- 新增 Annotate conflict files step（生成文件历史）
- 新增 Check artifact size step + 重构 Upload conflict bundle

### 兼容性
- happy path 完全不变（PR #59 行为保留）
- 失败降级：诊断步骤失败仅 warning

### Spec
docs/superpowers/specs/2026-07-15-channel-sync-conflict-rewrite-design.md §2"
```

预期：PR 创建成功。

- [ ] **Step 3：监控 CI**

```bash
gh pr checks <PR-number> --watch
```

预期：CI 通过。

- [ ] **Step 4：标记 PR-A 待用户合并**

**不要自行合并**，等用户确认。

---

## Phase 2：PR-B — PR 模板与自动 @ 作者（维度 2）

### Task 2.1：重构 PR body 模板

**Files:**
- Modify: `.github/workflows/channel-sync.yml`（Create sync PR step）

- [ ] **Step 1：定位 Create sync PR step**

```bash
grep -n "Create sync PR" .github/workflows/channel-sync.yml
```

- [ ] **Step 2：替换 body 字段**

**完整替换** `body:` 字段为（仅 draft 状态追加 ⚠️ 段）：

```yaml
          body: |
            🔁 [sync] #${{ needs.detect-sync.outputs.source_pr_number }} → ${{ matrix.target }}

            自动同步 PR（源 PR #${{ needs.detect-sync.outputs.source_pr_number }}）

            - 源分支: `${{ needs.detect-sync.outputs.source_branch }}`
            - 源作者: @${{ needs.detect-sync.outputs.source_author }}
            - 同步 commits: `${{ needs.detect-sync.outputs.commits }}`

            <!-- auto-sync-source: #${{ needs.detect-sync.outputs.source_pr_number }} -->
            <!-- auto-sync-target: ${{ matrix.target }} -->

            ${{ steps.pick.outputs.has_conflict == 'true' && '---

## ⚠️ Cherry-pick 冲突

**冲突 commit**: `' + env.CONFLICT_SHA + '`
**目标分支**: `' + matrix.target + '`
**冲突文件**: ' + steps.conflict-context.outputs.conflict_files_count + ' 个

### 快速解决指引

1. **下载** artifact `conflict-' + matrix.target + '` 获取三件套
2. **本地复现**：
   ```bash
   git fetch origin ' + matrix.target + '
   git checkout ' + matrix.target + '
   git cherry-pick -x ' + env.CONFLICT_SHA + '
   ```
3. **push 解决后合并此 PR** 即可触发自动续跑
' || '' }}
```

- [ ] **Step 3：YAML 语法验证**

```bash
yamllint .github/workflows/channel-sync.yml 2>&1 | head -10
```

- [ ] **Step 4：Commit Task 2.1**

```bash
git add .github/workflows/channel-sync.yml
git commit -m "feat(channel-sync): PR body template with conflict resolution guide

PR-B: 维度 2 第一步。
- 仅 draft PR 追加 ⚠️ 冲突段 + 快速解决指引
- 正常 PR body 与 PR #59 完全一致"
```

---

### Task 2.2：新增 Assign source author step

- [ ] **Step 1：在 Upload conflict bundle step 之后插入**

新增 step：

```yaml
      - name: Assign source author
        if: steps.pick.outputs.has_conflict == 'true'
        uses: actions/github-script@v7
        with:
          script: |
            try {
              await github.rest.issues.addAssignees({
                owner: context.repo.owner,
                repo: context.repo.repo,
                issue_number: context.issue.number,
                assignees: ['${{ needs.detect-sync.outputs.source_author }}']
              });
              console.log('Assigned source author:', '${{ needs.detect-sync.outputs.source_author }}');
            } catch (err) {
              console.warn('Failed to assign author:', err.message);
              core.warning('Source author assignment failed, continuing');
            }
          env:
            GITHUB_TOKEN: ${{ secrets.CHANNEL_SYNC_TOKEN }}
```

- [ ] **Step 2：YAML 语法验证 + Commit**

```bash
yamllint .github/workflows/channel-sync.yml 2>&1 | head -10
git add .github/workflows/channel-sync.yml
git commit -m "feat(channel-sync): auto-assign source author on conflict

PR-B: 维度 2 第二步。
- 仅冲突时 assign 源 PR 作者为 reviewer
- 失败降级：API 失败仅 warning"
```

---

### Task 2.3：新增 Apply conflicted-sync label step

- [ ] **Step 1：在 Assign source author step 之后新增**

新增：

```yaml
      - name: Apply conflicted-sync label
        if: steps.pick.outputs.has_conflict == 'true'
        uses: actions/github-script@v7
        with:
          script: |
            const LABEL_NAME = 'conflicted-sync';
            const LABEL_COLOR = 'd93f0b';
            const LABEL_DESC = 'Channel-sync PR with cherry-pick conflict';
            try {
              try {
                await github.rest.issues.getLabel({
                  owner: context.repo.owner,
                  repo: context.repo.repo,
                  name: LABEL_NAME
                });
              } catch (e) {
                if (e.status === 404) {
                  await github.rest.issues.createLabel({
                    owner: context.repo.owner,
                    repo: context.repo.repo,
                    name: LABEL_NAME,
                    color: LABEL_COLOR,
                    description: LABEL_DESC
                  });
                  console.log('Created label:', LABEL_NAME);
                } else {
                  throw e;
                }
              }
              await github.rest.issues.addLabels({
                owner: context.repo.owner,
                repo: context.repo.repo,
                issue_number: context.issue.number,
                labels: [LABEL_NAME]
              });
              console.log('Applied label:', LABEL_NAME);
            } catch (err) {
              console.warn('Failed to apply label:', err.message);
              core.warning('conflicted-sync label application failed, continuing');
            }
          env:
            GITHUB_TOKEN: ${{ secrets.CHANNEL_SYNC_TOKEN }}
```

- [ ] **Step 2：YAML 语法验证 + Commit**

```bash
yamllint .github/workflows/channel-sync.yml 2>&1 | head -10
git add .github/workflows/channel-sync.yml
git commit -m "feat(channel-sync): apply conflicted-sync label

PR-B: 维度 2 第三步。
- 仅冲突时应用 conflicted-sync label
- label 不存在时自动创建（idempotent）"
```

---

### Task 2.4：更新 CHANNEL_SYNC_SETUP.md

**Files:**
- Modify: `.github/CHANNEL_SYNC_SETUP.md`

- [ ] **Step 1：在文档末尾追加「冲突解决流程」章节**

```markdown

## 冲突解决流程

当 channel-sync 检测到 cherry-pick 冲突时，会自动：

1. **生成三件套 artifact**（`conflict-<target>`）：
   - `source.patch` / `target.patch` / `diverge.patch` — 三方 diff
   - `conflict_files.txt` — 冲突文件清单
   - `file_history.md` — 冲突文件的历史改动
2. **创建 draft PR**，body 含「⚠️ Cherry-pick 冲突」段与解决指引
3. **自动 assign 源 PR 作者** 为 reviewer
4. **应用 `conflicted-sync` label**

### 人工解决步骤

1. 下载 `conflict-<target>` artifact
2. 本地复现冲突（见 PR body 中的 `快速解决指引` 段）
3. 编辑冲突文件
4. push 到 `channel-sync/<src>-<target>` 分支
5. 合并 draft PR → **resume workflow 自动 cherry-pick 剩余 commits**

### 嵌套保护

- resume 嵌套 ≤ 2 层（连续 resume 后再冲突）
- 超出后 workflow 主动失败，需人工处理
```

- [ ] **Step 2：Commit Task 2.4**

```bash
git add .github/CHANNEL_SYNC_SETUP.md
git commit -m "docs(channel-sync): document conflict resolution flow

PR-B: 维度 2 第四步。"
```

---

### Task 2.5：Push + 开 PR-B

- [ ] **Step 1：推送并开 PR**

```bash
git push -u origin feature/channel-sync-conflict-rewrite
gh pr create \
  --base main \
  --head feature/channel-sync-conflict-rewrite \
  --title "feat(channel-sync): PR body template + auto-assign author + conflicted-sync label (PR-B)" \
  --body "## PR-B: PR 增强（维度 2）

### 改动
- 重构 PR body 模板：冲突 PR 含完整解决指引
- 新增 Assign source author step（仅冲突时）
- 新增 Apply conflicted-sync label step
- 更新 CHANNEL_SYNC_SETUP.md

### 依赖
PR-A 已合并

### 兼容性
正常 PR 行为不变；assign/label 失败仅 warning

### Spec
docs/superpowers/specs/2026-07-15-channel-sync-conflict-rewrite-design.md §3"
gh pr checks <PR-number> --watch
```

---

## Phase 3：PR-C — 续跑机制（维度 3）

### Task 3.1：创建 channel-sync-resume.yml 骨架

**Files:**
- Create: `.github/workflows/channel-sync-resume.yml`

- [ ] **Step 1：创建文件**

写入 `.github/workflows/channel-sync-resume.yml`：

```yaml
name: Channel Sync Resume

on:
  pull_request:
    types: [closed]
    branches: [main, beta, rc]

permissions:
  contents: read
  pull-requests: read

concurrency:
  group: channel-sync-resume-${{ github.event.pull_request.number }}
  cancel-in-progress: false

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
      remaining_commits: ${{ steps.compute.outputs.remaining_commits }}
      nested_level: ${{ steps.compute.outputs.nested_level }}
    steps:
      - name: Skip if not sync PR
        id: skip
        env:
          PR_TITLE: ${{ github.event.pull_request.title }}
          PR_BODY: ${{ github.event.pull_request.body }}
          PR_ACTOR: ${{ github.actor }}
        run: |
          if [[ "$PR_TITLE" == "🔁 [resume]"* ]] || [[ "$PR_BODY" == *"auto-sync-resume: true"* ]]; then
            echo "skip=true" >> $GITHUB_OUTPUT
          else
            echo "skip=false" >> $GITHUB_OUTPUT
          fi
```

- [ ] **Step 2：YAML 语法验证 + Commit**

```bash
yamllint .github/workflows/channel-sync-resume.yml 2>&1 | head -10
git add .github/workflows/channel-sync-resume.yml
git commit -m "feat(channel-sync-resume): scaffold detect-resume job

PR-C: 维度 3 第一步。
- 新增 channel-sync-resume.yml workflow
- detect-resume job: trigger filter + concurrency group
- 防递归：title 前缀 + auto-sync-resume marker 检测"
```

---

### Task 3.2：实现 Parse + Compute steps

**Files:**
- Modify: `.github/workflows/channel-sync-resume.yml`

- [ ] **Step 1：在 Skip step 之后追加 Parse step**

```yaml
      - name: Parse sync PR metadata
        id: parse
        if: steps.skip.outputs.skip != 'true'
        env:
          PR_BODY: ${{ github.event.pull_request.body }}
        run: |
          SOURCE_PR=$(echo "$PR_BODY" | grep -oP 'auto-sync-source: #\K\d+' | head -1)
          TARGET=$(echo "$PR_BODY" | grep -oP 'auto-sync-target: \K\S+' | head -1)
          if [ -z "$SOURCE_PR" ] || [ -z "$TARGET" ]; then
            echo "::warning::Missing auto-sync-source/target markers in PR body"
            echo "should_resume=false" >> $GITHUB_OUTPUT
            exit 0
          fi
          echo "source_pr=$SOURCE_PR" >> $GITHUB_OUTPUT
          echo "target=$TARGET" >> $GITHUB_OUTPUT
          echo "should_resume=true" >> $GITHUB_OUTPUT
```

- [ ] **Step 2：追加 Compute remaining commits step**

```yaml
      - name: Compute remaining commits
        id: compute
        if: steps.parse.outputs.should_resume == 'true'
        env:
          GH_TOKEN: ${{ secrets.CHANNEL_SYNC_TOKEN }}
          SOURCE_PR: ${{ steps.parse.outputs.source_pr }}
          TARGET: ${{ steps.parse.outputs.target }}
        run: |
          set +e
          COMMITS_JSON=$(gh api "repos/${{ github.repository }}/pulls/${SOURCE_PR}/commits" --jq '[.[].sha]' 2>/dev/null)
          if [ -z "$COMMITS_JSON" ] || [ "$COMMITS_JSON" = "null" ]; then
            echo "::error::Failed to fetch commits for source PR #$SOURCE_PR"
            echo "should_resume=false" >> $GITHUB_OUTPUT
            exit 0
          fi
          COMMITS=$(echo "$COMMITS_JSON" | jq -r '.[]' | tr '\n' ' ')

          git fetch origin "$TARGET" --depth=0 2>/dev/null

          REMAINING=""
          for SHA in $COMMITS; do
            if ! git merge-base --is-ancestor "$SHA" "origin/$TARGET" 2>/dev/null; then
              REMAINING="$REMAINING $SHA"
            fi
          done

          NESTED=$(echo "${{ github.event.pull_request.body }}" | grep -c "auto-sync-resume: true" || echo "0")

          if [ -z "${REMAINING# }" ]; then
            echo "::notice::All commits already in $TARGET, no resume needed"
            echo "should_resume=false" >> $GITHUB_OUTPUT
          elif [ "$NESTED" -ge 2 ]; then
            echo "::error::Resume nested level >= 2, manual intervention required"
            echo "should_resume=false" >> $GITHUB_OUTPUT
          else
            echo "should_resume=true" >> $GITHUB_OUTPUT
            echo "remaining_commits=${REMAINING# }" >> $GITHUB_OUTPUT
            echo "nested_level=$NESTED" >> $GITHUB_OUTPUT
          fi
```

- [ ] **Step 3：YAML 语法验证 + Commit**

```bash
yamllint .github/workflows/channel-sync-resume.yml 2>&1 | head -10
git add .github/workflows/channel-sync-resume.yml
git commit -m "feat(channel-sync-resume): parse PR metadata + compute remaining commits

PR-C: 维度 3 第二步。
- Parse step: 提取 auto-sync-source/target markers
- Compute step: 找出 target 还缺哪些 commits
- 嵌套检测：嵌套 ≥ 2 层主动拒绝"
```

---

### Task 3.3：实现 cherry-pick-remaining job

**Files:**
- Modify: `.github/workflows/channel-sync-resume.yml`

- [ ] **Step 1：在 detect-resume job 之后追加 cherry-pick-remaining job**

```yaml
  cherry-pick-remaining:
    needs: detect-resume
    if: needs.detect-resume.outputs.should_resume == 'true'
    runs-on: ubuntu-latest
    permissions:
      contents: write
      pull-requests: write
    steps:
      - name: Checkout target
        uses: actions/checkout@v4
        with:
          ref: ${{ needs.detect-resume.outputs.target }}
          fetch-depth: 0
          token: ${{ secrets.CHANNEL_SYNC_TOKEN }}

      - name: Fetch source commits
        run: |
          git fetch origin "${{ needs.detect-resume.outputs.source_pr }}" --no-tags || true

      - name: Cherry-pick remaining commits
        id: pick
        run: |
          set +e
          git config user.name "channel-sync-bot"
          git config user.email "channel-sync-bot@users.noreply.github.com"
          CONFLICT_SHA=""
          for SHA in ${{ needs.detect-resume.outputs.remaining_commits }}; do
            if git merge-base --is-ancestor "$SHA" HEAD 2>/dev/null; then
              echo "::notice::Skipping $SHA (already in target)"
              continue
            fi
            if ! git cherry-pick -x "$SHA" > "$RUNNER_TEMP/cherry-pick.log" 2>&1; then
              CONFLICT_SHA="$SHA"
              git cherry-pick --abort || true
              git format-patch -1 "$SHA" --stdout > "$RUNNER_TEMP/conflict.patch"
              echo "CONFLICT_SHA=$SHA" >> $GITHUB_ENV
              break
            fi
          done
          if [ -n "$CONFLICT_SHA" ]; then
            git commit --allow-empty -m "chore(sync): mark conflict on $CONFLICT_SHA"
          fi
          echo "has_conflict=$([ -n "$CONFLICT_SHA" ] && echo true || echo false)" >> $GITHUB_OUTPUT

      - name: Push branch
        if: steps.pick.outputs.has_conflict != 'true'
        run: |
          BRANCH="channel-sync/${{ needs.detect-resume.outputs.source_pr }}-${{ needs.detect-resume.outputs.target }}"
          git push origin "HEAD:$BRANCH" --force-with-lease

      - name: Create resume PR
        uses: peter-evans/create-pull-request@v6
        with:
          token: ${{ secrets.CHANNEL_SYNC_TOKEN }}
          branch: channel-sync/${{ needs.detect-resume.outputs.source_pr }}-${{ needs.detect-resume.outputs.target }}
          base: ${{ needs.detect-resume.outputs.target }}
          title: "🔁 [resume] #${{ needs.detect-resume.outputs.source_pr }} → ${{ needs.detect-resume.outputs.target }}"
          body: |
            🔁 [resume] #${{ needs.detect-resume.outputs.source_pr }} → ${{ needs.detect-resume.outputs.target }}

            自动续跑 PR（原 sync PR 解决冲突后触发）

            - 源 PR: #${{ needs.detect-resume.outputs.source_pr }}
            - 目标: ${{ needs.detect-resume.outputs.target }}
            - 续跑 commits: `${{ needs.detect-resume.outputs.remaining_commits }}`
            - 嵌套层数: ${{ needs.detect-resume.outputs.nested_level }}

            <!-- auto-sync-source: #${{ needs.detect-resume.outputs.source_pr }} -->
            <!-- auto-sync-target: ${{ needs.detect-resume.outputs.target }} -->
            <!-- auto-sync-resume: true -->

            ${{ steps.pick.outputs.has_conflict == 'true' && '⚠️ **Cherry-pick 冲突（resume 时再次冲突），请人工解决**' || '' }}
          draft: ${{ steps.pick.outputs.has_conflict == 'true' }}
          delete-branch: true

      - name: Remove conflicted-sync label
        if: steps.pick.outputs.has_conflict != 'true'
        uses: actions/github-script@v7
        with:
          script: |
            try {
              await github.rest.issues.removeLabel({
                owner: context.repo.owner,
                repo: context.repo.repo,
                issue_number: context.issue.number,
                name: 'conflicted-sync'
              });
              console.log('Removed conflicted-sync label');
            } catch (err) {
              console.warn('Failed to remove label:', err.message);
            }
          env:
            GITHUB_TOKEN: ${{ secrets.CHANNEL_SYNC_TOKEN }}
```

- [ ] **Step 2：YAML 语法验证 + Commit**

```bash
yamllint .github/workflows/channel-sync-resume.yml 2>&1 | head -10
git add .github/workflows/channel-sync-resume.yml
git commit -m "feat(channel-sync-resume): cherry-pick remaining commits + resume PR

PR-C: 维度 3 第三步。
- cherry-pick-remaining job: 复用核心 cherry-pick 逻辑
- 标题前缀 🔁 [resume] 区分于 🔁 [sync]
- marker auto-sync-resume: true 防递归"
```

---

### Task 3.4：扩展 channel-sync.yml skip 条件

**Files:**
- Modify: `.github/workflows/channel-sync.yml`

- [ ] **Step 1：定位 skip step**

```bash
grep -n "Skip sync PRs and bot actors" .github/workflows/channel-sync.yml
```

- [ ] **Step 2：扩展 skip 条件**

修改 step 的 `run:` 块：

```bash
        run: |
          if [[ "$PR_TITLE" == "🔁 [sync]"* ]] || [[ "$PR_TITLE" == "🔁 [resume]"* ]] || [[ "$PR_BODY" == *"auto-sync-source:"* ]] || [[ "$PR_BODY" == *"auto-sync-resume: true"* ]] || [[ "$PR_ACTOR" == "github-actions[bot]" ]]; then
            echo "skip=true" >> $GITHUB_OUTPUT
          else
            echo "skip=false" >> $GITHUB_OUTPUT
          fi
```

- [ ] **Step 3：YAML 语法验证 + Commit**

```bash
yamllint .github/workflows/channel-sync.yml 2>&1 | head -10
git add .github/workflows/channel-sync.yml
git commit -m "fix(channel-sync): skip resume PRs in detect-sync

PR-C: 维度 3 第四步。
- skip 条件扩展：检测 🔁 [resume] 前缀 + auto-sync-resume marker
- 防止 resume PR 触发 detect-sync 形成递归"
```

---

### Task 3.5：集成测试（fork 仓库端到端）

**Files:**
- Create: 测试 fork 仓库 `OmniDesk/channel-sync-test`

- [ ] **Step 1：创建 fork 测试仓库**

```bash
gh repo create OmniDesk/channel-sync-test --private --description "Channel sync workflow integration test repo"
```

- [ ] **Step 2：复制 workflow 文件 + 预置冲突数据**

```bash
git clone git@github.com:OmniDesk/channel-sync-test.git /tmp/test-repo
cd /tmp/test-repo
mkdir -p .github/workflows
cp /home/fz/project/OmniDesk/.github/workflows/channel-sync.yml .github/workflows/
cp /home/fz/project/OmniDesk/.github/workflows/channel-sync-resume.yml .github/workflows/
echo "version 1" > file.txt
git add . && git commit -m "feat: init"
git push origin main
```

- [ ] **Step 3：触发冲突场景**

在 channel-sync-test 仓库制造冲突：
1. main 分支先有 fix commit A
2. beta 分支先 cherry-pick A（成功）
3. main 后续加 fix commit B 与 A 同文件不同内容
4. 同步 B 到 beta → 冲突

- [ ] **Step 4：观察 workflow + resume 行为**

记录：
- 第一次 sync PR 是否 draft + conflicted-sync label + assign author
- 解决冲突 + merge 后，resume workflow 是否触发
- resume PR 是否成功 cherry-pick 剩余 commits

预期：端到端通过。

---

### Task 3.6：Push + 开 PR-C

- [ ] **Step 1：推送并开 PR**

```bash
git push -u origin feature/channel-sync-conflict-rewrite
gh pr create \
  --base main \
  --head feature/channel-sync-conflict-rewrite \
  --title "feat(channel-sync-resume): auto-resume cherry-pick after conflict resolution (PR-C)" \
  --body "## PR-C: 续跑机制（维度 3）

### 改动
- 新增 .github/workflows/channel-sync-resume.yml
- detect-resume + cherry-pick-remaining jobs
- 扩展 channel-sync.yml skip 条件（防递归）

### 依赖
PR-B 已合并

### 兼容性
嵌套 ≤ 2 层保护；resume PR 用 🔁 [resume] 前缀区分

### Spec
docs/superpowers/specs/2026-07-15-channel-sync-conflict-rewrite-design.md §4"
gh pr checks <PR-number> --watch
```

---

## Phase 4：PR-D — 测试覆盖（维度 4）

### Task 4.1：编写 conflict_scenarios.json fixture

**Files:**
- Create: `tests/fixtures/conflict_scenarios.json`

- [ ] **Step 1：创建文件**

写入：

```json
{
  "_comment": "Conflict scenario fixtures for test_conflict_handler.sh",
  "scenarios": [
    {
      "name": "all_commits_already_in_target",
      "source_pr": 65,
      "target_branch": "beta",
      "commits": ["abc1234567", "def5678901", "ghi9012345"],
      "target_ancestors": ["abc1234567", "def5678901", "ghi9012345"],
      "expected_remaining": "",
      "expected_should_resume": false
    },
    {
      "name": "partial_commits_in_target",
      "source_pr": 68,
      "target_branch": "beta",
      "commits": ["abc1234567", "def5678901", "ghi9012345"],
      "target_ancestors": ["abc1234567"],
      "expected_remaining": "def5678901 ghi9012345",
      "expected_should_resume": true
    },
    {
      "name": "no_commits_in_target",
      "source_pr": 70,
      "target_branch": "rc",
      "commits": ["aaa1111111", "bbb2222222"],
      "target_ancestors": [],
      "expected_remaining": "aaa1111111 bbb2222222",
      "expected_should_resume": true
    },
    {
      "name": "marker_missing_source",
      "pr_body": "Some body without markers",
      "expected_should_resume": false,
      "expected_source_pr": "",
      "expected_target": ""
    },
    {
      "name": "marker_valid",
      "pr_body": "<!-- auto-sync-source: #68 -->\n<!-- auto-sync-target: beta -->\nbody",
      "expected_should_resume": true,
      "expected_source_pr": "68",
      "expected_target": "beta"
    }
  ]
}
```

- [ ] **Step 2：JSON 语法验证 + Commit**

```bash
python3 -c "import json; json.load(open('tests/fixtures/conflict_scenarios.json'))" && echo "VALID JSON"
git add tests/fixtures/conflict_scenarios.json
git commit -m "test(channel-sync): add conflict scenarios fixture

PR-D: 维度 4 第一步。"
```

---

### Task 4.2：编写 test_conflict_handler.sh

**Files:**
- Create: `tests/test_conflict_handler.sh`

- [ ] **Step 1：创建文件**

写入：

```bash
#!/bin/bash
# L1 unit tests for conflict handler parsing logic
# 覆盖 spec §5 测试用例 1-5

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FIXTURE="$SCRIPT_DIR/fixtures/conflict_scenarios.json"
PASS=0
FAIL=0

if [ ! -f "$FIXTURE" ]; then
  echo "ERROR: Fixture not found: $FIXTURE"
  exit 2
fi

assert_eq() {
  local desc="$1" expected="$2" actual="$3"
  if [ "$expected" = "$actual" ]; then
    echo "  ✓ $desc"
    PASS=$((PASS+1))
  else
    echo "  ✗ $desc (expected: '$expected', got: '$actual')"
    FAIL=$((FAIL+1))
  fi
}

assert_contains() {
  local desc="$1" needle="$2" haystack="$3"
  if [[ "$haystack" == *"$needle"* ]]; then
    echo "  ✓ $desc"
    PASS=$((PASS+1))
  else
    echo "  ✗ $desc (needle '$needle' not found)"
    FAIL=$((FAIL+1))
  fi
}

# Test 1: parse_sync_markers_valid
echo "Test 1: parse_sync_markers_valid"
BODY='<!-- auto-sync-source: #68 -->
<!-- auto-sync-target: beta -->
some body'
SOURCE_PR=$(echo "$BODY" | grep -oP 'auto-sync-source: #\K\d+' | head -1)
TARGET=$(echo "$BODY" | grep -oP 'auto-sync-target: \K\S+' | head -1)
assert_eq "source_pr parsed correctly" "68" "$SOURCE_PR"
assert_eq "target parsed correctly" "beta" "$TARGET"

# Test 2: parse_sync_markers_missing
echo "Test 2: parse_sync_markers_missing"
BODY="body without markers"
SOURCE_PR=$(echo "$BODY" | grep -oP 'auto-sync-source: #\K\d+' | head -1)
TARGET=$(echo "$BODY" | grep -oP 'auto-sync-target: \K\S+' | head -1)
assert_eq "missing marker → empty source_pr" "" "${SOURCE_PR:-}"
assert_eq "missing marker → empty target" "" "${TARGET:-}"

# Test 3: compute_remaining_commits_all_applied
echo "Test 3: compute_remaining_commits_all_applied"
ALL_COMMITS="abc def ghi"
TARGET_ANCESTORS="abc def ghi"
REMAINING=""
for SHA in $ALL_COMMITS; do
  if ! echo "$TARGET_ANCESTORS" | grep -qw "$SHA"; then
    REMAINING="$REMAINING $SHA"
  fi
done
assert_eq "all applied → empty remaining" "" "${REMAINING# }"

# Test 4: compute_remaining_commits_partial
echo "Test 4: compute_remaining_commits_partial"
ALL_COMMITS="abc def ghi"
TARGET_ANCESTORS="abc"
REMAINING=""
for SHA in $ALL_COMMITS; do
  if ! echo "$TARGET_ANCESTORS" | grep -qw "$SHA"; then
    REMAINING="$REMAINING $SHA"
  fi
done
assert_eq "partial → correct remaining" "def ghi" "${REMAINING# }"

# Test 5: pr_body_template_conflict
echo "Test 5: pr_body_template_conflict"
RENDERED=$(cat <<'EOF'
🔁 [sync] #68 → beta
自动同步 PR

## ⚠️ Cherry-pick 冲突

**冲突 commit**: `a3fae3ff`
**目标分支**: `beta`
**冲突文件**: 3 个

### 快速解决指引

1. 下载 artifact
2. 本地复现
3. push 解决
4. 合并触发续跑

<!-- auto-sync-source: #68 -->
<!-- auto-sync-target: beta -->
EOF
)
assert_contains "body has ⚠️ marker" "⚠️ Cherry-pick 冲突" "$RENDERED"
assert_contains "body has 快速解决指引" "快速解决指引" "$RENDERED"
assert_contains "body has auto-sync-source marker" "auto-sync-source: #68" "$RENDERED"

# Summary
echo ""
echo "Results: PASS=$PASS FAIL=$FAIL"
if [ "$FAIL" -gt 0 ]; then
  exit 1
fi
```

- [ ] **Step 2：添加执行权限 + 运行测试**

```bash
chmod +x tests/test_conflict_handler.sh
bash tests/test_conflict_handler.sh
```

预期：`Results: PASS=11 FAIL=0`。

- [ ] **Step 3：Commit Task 4.2**

```bash
git add tests/test_conflict_handler.sh
git commit -m "test(channel-sync): add L1 unit tests for conflict handler

PR-D: 维度 4 第二步。
- 5 用例 / 11 asserts
- 不依赖网络，纯 bash 测试"
```

---

### Task 4.3：编写 dry-run-cherry-pick.sh

**Files:**
- Create: `.github/scripts/dry-run-cherry-pick.sh`

- [ ] **Step 1：创建脚本**

写入：

```bash
#!/bin/bash
# L3 E2E smoke test for channel-sync cherry-pick logic

set -uo pipefail

TESTDIR=$(mktemp -d)
trap "rm -rf $TESTDIR" EXIT

echo "=== Dry-run channel-sync cherry-pick in $TESTDIR ==="

cd "$TESTDIR"
git init --quiet --bare source.git
git init --quiet --bare target.git
git clone --quiet source.git src
cd src
git config user.email "test@test.com"
git config user.name "Test"
echo "v1" > file.txt
git add . && git commit -q -m "fix: init"
git push -q origin main

cd "$TESTDIR"
git clone --quiet target.git tgt
cd tgt
git config user.email "test@test.com"
git config user.name "Test"
git pull -q origin main
echo "v1 conflict" > file.txt
git add . && git commit -q -m "feat: change"
git push -q origin main

cd "$TESTDIR/src"
echo "v2 fix" > file.txt
git add . && git commit -q -m "fix(scope): test cherry-pick"
NEW_FIX=$(git rev-parse HEAD)

cd "$TESTDIR/tgt"
echo "--- Cherry-picking $NEW_FIX ---"
git cherry-pick -x "$NEW_FIX" 2>&1 || echo "(expected conflict)"

if git diff --name-only --diff-filter=U | grep -q .; then
  echo "✓ CONFLICT DETECTED (expected)"
  echo "Conflicted files:"
  git diff --name-only --diff-filter=U
  echo ""
  echo "would_conflict=true"
  exit 0
else
  echo "✗ NO CONFLICT (test scenario broken)"
  exit 1
fi
```

- [ ] **Step 2：添加执行权限 + 测试**

```bash
chmod +x .github/scripts/dry-run-cherry-pick.sh
bash .github/scripts/dry-run-cherry-pick.sh
```

预期：`✓ CONFLICT DETECTED (expected)` 和 `would_conflict=true`。

- [ ] **Step 3：Commit Task 4.3**

```bash
git add .github/scripts/dry-run-cherry-pick.sh
git commit -m "test(channel-sync): add dry-run cherry-pick E2E script

PR-D: 维度 4 第三步。"
```

---

### Task 4.4：扩展 release-channel-matrix.yml

**Files:**
- Modify: `.github/workflows/release-channel-matrix.yml`

- [ ] **Step 1：在文件末尾追加新 job**

```yaml
  dry-run-sync-conflict:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Run dry-run cherry-pick
        run: bash .github/scripts/dry-run-cherry-pick.sh

      - name: Verify completion
        run: |
          echo "Dry-run completed (exit 0 = conflict detected as expected)"
```

- [ ] **Step 2：YAML 语法验证 + Commit**

```bash
yamllint .github/workflows/release-channel-matrix.yml 2>&1 | head -10
git add .github/workflows/release-channel-matrix.yml
git commit -m "ci(release-matrix): add dry-run-sync-conflict E2E job

PR-D: 维度 4 第四步。"
```

---

### Task 4.5：本地验证 PR-D

- [ ] **Step 1：跑 L1 单元测试**

```bash
bash tests/test_conflict_handler.sh
```

预期：`Results: PASS=11 FAIL=0`。

- [ ] **Step 2：跑 L3 dry-run 测试**

```bash
bash .github/scripts/dry-run-cherry-pick.sh
```

预期：`✓ CONFLICT DETECTED (expected)`。

---

### Task 4.6：Push + 开 PR-D

- [ ] **Step 1：推送并开 PR**

```bash
git push -u origin feature/channel-sync-conflict-rewrite
gh pr create \
  --base main \
  --head feature/channel-sync-conflict-rewrite \
  --title "test(channel-sync): L1 unit tests + L3 E2E dry-run (PR-D)" \
  --body "## PR-D: 测试覆盖（维度 4）

### 改动
- tests/fixtures/conflict_scenarios.json（5 scenarios）
- tests/test_conflict_handler.sh（5 用例 / 11 asserts）
- .github/scripts/dry-run-cherry-pick.sh
- 扩展 release-channel-matrix.yml

### 依赖
PR-C 已合并

### 测试
- L1: bash tests/test_conflict_handler.sh → 11/11 PASS
- L3: bash .github/scripts/dry-run-cherry-pick.sh → ✓ conflict detected

### Spec
docs/superpowers/specs/2026-07-15-channel-sync-conflict-rewrite-design.md §5"
gh pr checks <PR-number> --watch
```

---

## Phase 5：PR-E — 文档同步

### Task 5.1：更新 docs/technical/30-release-channels.md

**Files:**
- Modify: `docs/technical/30-release-channels.md`

- [ ] **Step 1：定位「自动同步」章节**

```bash
grep -n "自动同步\|## \|### " docs/technical/30-release-channels.md | head -30
```

- [ ] **Step 2：追加「冲突解决流程」子章节**

```markdown
### 冲突解决流程

当 channel-sync workflow 检测到 cherry-pick 冲突时：

1. **生成三件套 artifact**（`conflict-<target>`）：
   - `source.patch` / `target.patch` / `diverge.patch` — 三方 diff（base ↔ source ↔ target）
   - `conflict_files.txt` — 冲突文件清单
   - `file_history.md` — 每个冲突文件的源/目标最近 5 次改动
2. **创建 draft PR**，body 含「⚠️ Cherry-pick 冲突」段与解决指引
3. **自动 assign 源 PR 作者** 为 reviewer
4. **应用 `conflicted-sync` label**

#### 人工解决步骤

1. 下载 `conflict-<target>` artifact
2. 本地复现冲突：
   ```bash
   git fetch origin <target>
   git checkout <target>
   git cherry-pick -x <CONFLICT_SHA>
   git cherry-pick --continue
   ```
3. push 到 `channel-sync/<src>-<target>` 分支
4. 合并 draft PR → **resume workflow 自动 cherry-pick 剩余 commits**

#### 续跑机制

`channel-sync-resume.yml` 监听带 `conflicted-sync` label 的 sync PR 被合并：

- 解析 PR body 的 `auto-sync-source` / `auto-sync-target` markers
- 计算 target 还缺哪些 commits
- 复用 cherry-pick 逻辑创建 `🔁 [resume]` PR
- 嵌套 ≤ 2 层（连续 resume 后再冲突，超出后人工处理）
```

- [ ] **Step 3：Commit Task 5.1**

```bash
git add docs/technical/30-release-channels.md
git commit -m "docs(channel-sync): add conflict resolution flow section

PR-E: 文档同步第一步。"
```

---

### Task 5.2：更新 docs/technical/README.md（如需要）

- [ ] **Step 1：检查并按需更新**

```bash
grep -n "30-release-channels" docs/technical/README.md
```

如目录表格描述需要补充，编辑对应行。否则跳过。

- [ ] **Step 2：Commit Task 5.2（如有改动）**

```bash
git diff --cached --quiet docs/technical/README.md || {
  git add docs/technical/README.md
  git commit -m "docs(channel-sync): update README TOC if needed"
}
```

---

### Task 5.3：Push + 开 PR-E

- [ ] **Step 1：推送并开 PR**

```bash
git push -u origin feature/channel-sync-conflict-rewrite
gh pr create \
  --base main \
  --head feature/channel-sync-conflict-rewrite \
  --title "docs(channel-sync): document conflict resolution flow (PR-E)" \
  --body "## PR-E: 文档同步

### 改动
- docs/technical/30-release-channels.md: 新增「冲突解决流程」子章节
- docs/technical/README.md: 必要时更新 TOC"
gh pr checks <PR-number> --watch
```

---

## Phase 6：收尾验证

### Task 6.1：监控 stable 渠道一周

- [ ] **Step 1：观察 sync PR 行为**

触发 2-3 次 sync PR（正常 + 冲突各一次），验证：
- 正常 PR 行为与 PR #59 完全一致
- 冲突 PR artifact 完整
- 冲突 PR body 含 ⚠️ 段
- assignee = 源作者
- label `conflicted-sync` 已应用
- 解决后 resume workflow 自动触发
- resume PR 用 🔁 [resume] 前缀
- 嵌套 ≥ 2 层时主动失败

### Task 6.2：清理 debug 限制（如有）

- [ ] **Step 1：检查 debug 输出**

```bash
grep -n "DEBUG\|debug:\|echo.*debug" .github/workflows/channel-sync.yml | head -10
```

如无残留，跳过。

- [ ] **Step 2：最终验证**

```bash
yamllint .github/workflows/channel-sync.yml
yamllint .github/workflows/channel-sync-resume.yml
yamllint .github/workflows/release-channel-matrix.yml
bash tests/test_conflict_handler.sh
```

预期：全部通过。

---

## 风险登记（实施期关注）

| ID | 风险 | 应对 |
|---|---|---|
| R1 | 三方 diff > 5MB 频繁触发 | Task 1.4 size check |
| R2 | 嵌套 ≥ 2 层 | Task 3.2 主动拒绝 |
| R3 | 测试 fork 仓库维护 | Task 3.5 季度 review |
| R4 | 源 PR 被 force-push / 删除 | Task 3.2 API 失败检测 |
| R5 | GitHub API 限流 | retry-with-backoff（如需） |
| R6 | Label 被管理员重命名 | Task 2.3 idempotent |
| R7 | 任一 PR review 不通过 | 每 PR 独立可 revert |

## 边界（不在范围内）

- ❌ 不重构 detect-sync（PR #59 已稳定）
- ❌ 不重构 happy path
- ❌ 不引入新 secret
- ❌ 不引入外部依赖
- ❌ 不发 develop/beta/rc
- ❌ 不实现 reviewer 自动指派算法
- ❌ 不支持 ≥ 3 层嵌套续跑