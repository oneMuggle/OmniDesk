# Task 3.2 Report — 实现 Parse + Compute steps

## Status: DONE

## Summary
在 `feature/channel-sync-conflict-rewrite` 分支的 `detect-resume` job 中追加两个 step:
1. **Parse sync PR metadata** (id: `parse`) — 从 PR body 提取 `auto-sync-source` / `auto-sync-target` markers
2. **Compute remaining commits** (id: `compute`) — 调 `gh api` 拿 source PR commit 列表, 用 `git merge-base --is-ancestor` 检测哪些 commits 在 target 中还缺, 并做嵌套检测 (≥ 2 层主动拒绝)

## 改动文件
- `.github/workflows/channel-sync-resume.yml` (+57 行)

## 验证
- [x] YAML 语法校验通过 (python3 `yaml.safe_load`)
- [x] Step 顺序: skip → parse → compute
- [x] Parse step `id: parse`, `if: steps.skip.outputs.skip != 'true'` ✓
- [x] Compute step `id: compute`, `if: steps.parse.outputs.should_resume == 'true'` ✓
- [x] Compute step 使用 `set +e`, 所有 API 调用都有 `2>/dev/null` 抑制错误
- [x] 三个输出 `should_resume`, `source_pr`, `target` 来自 parse step; `remaining_commits`, `nested_level` 来自 compute step — 与 job outputs 完全对齐
- [x] 嵌套检测: `grep -c "auto-sync-resume: true"` 计算 PR body 中 marker 出现次数, ≥2 层报错并 `should_resume=false`
- [x] 只有 1 个新 commit

## Commit
- `d452cc79` feat(channel-sync-resume): parse PR metadata + compute remaining commits

## Notes
- yamllint 报 line-too-long 警告, 但都是 shell 脚本内嵌行, GitHub Actions 标准做法;与原文件已有的 PR 标题 emoji 行保持一致风格, 不影响 workflow 执行。
- Compute step 的 `set +e` 显式开启, 配合 `2>/dev/null` 抑制 API 失败的中断;失败时通过 `::error::`/`::notice::` 日志标注, 但不 fail job (用 `exit 0` + `should_resume=false` 让后续 step 短路)。

---

## 2026-07-16 Peer Review 修复

### Status: DONE

### 修复内容

1. PR body 仅通过 `PR_BODY` 环境变量进入 shell,不再内联 GitHub expression。
2. compute 前增加 `actions/checkout@v4` 与 `fetch-depth: 0`;移除无效 `--depth=0`,并显式检查 fetch 失败。
3. job `should_resume` output 优先采用 compute 结果,保留 parse fallback。
4. `gh api`、JSON 解析、git fetch/log/merge-base 硬失败均写入 error annotation 并 `exit 1`。
5. job filter 覆盖 `🔁 [resume]` 与 resume marker;修正 `grep -c` 的双 `0` 问题。
6. 使用 `git log --fixed-strings --grep="(cherry picked from commit $SHA)"` 识别 `cherry-pick -x` 等价提交,再以 merge-base 处理直接祖先。

### 附加加固

- 拒绝 fork PR;marker target 必须等于可信的 PR base ref,防止 refspec 注入。
- Pull commits API 启用分页聚合,并沿用 `fix|perf|refactor` 提交类型过滤。
- 增加 YAML document start 与局部 yamllint 规则标注。

### 验证

- [x] 8 项结构化回归断言通过（6 个指定缺陷 + target 安全 + API 完整性）
- [x] `yaml.safe_load` 解析通过
- [x] `yamllint` 通过（0 error,0 warning）
- [x] Parse/Compute 内嵌 Bash `bash -n` 通过
- [x] jq 多页提交类型过滤样例通过
- [x] 恶意多行 PR body 保持为纯数据,嵌套计数 2/0 正确
- [x] `git diff --check` 通过
- [x] 最终代码审查与安全审查:0 CRITICAL / 0 HIGH

### Commit

- `fix(channel-sync-resume): address 6 issues from peer review`

### Notes

- 本节取代上方初始实现报告中关于 `set +e`、`exit 0`、skip step 和旧 output 映射的说明。
- Task 3.3 生成后续 resume PR 时需按设计传递嵌套 marker,以便本步骤的 `nested_level >= 2` 门控生效。