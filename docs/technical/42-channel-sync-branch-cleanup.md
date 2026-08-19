# 42 channel-sync 远程分支自动清理

## 背景

`channel-sync.yml` workflow 为每个 merge 到 develop 的 PR,在远端开两个长期归档分支:

- `channel-sync/<PR号>-beta`
- `channel-sync/<PR号>-rc`

这些分支承担"同步可追溯 + 可重放"的职责——bot 持续 force-push 维护独立 sync PR 池,与原始 PR 生命周期完全脱钩。

### 历史积压

历史上这些分支没有自动清理机制,长期累积(峰值约 108 个)。后果:

- 远程分支列表膨胀,影响 GitHub UI/CLI 加载
- 没有实际功能用途(半年以上归档几乎无人回查)

## 触发条件

| 触发方式 | 说明 |
|---|---|
| cron | `42 4 * * *`(每天 04:42 UTC,与 `stale-sync` 错开 1h) |
| workflow_dispatch | 手动触发,`dry_run` input(默认 `true`) |

## 清理规则(必须全部满足)

1. 分支名匹配 `^channel-sync/.+`
2. 不在 `.github/channel-sync-keep.yml` 的豁免清单中
3. 分支 head commit 的 `committer.date` 距今 ≥ 14 天

### 设计折中(对比设计稿)

设计稿最初 5 条 AND 门(含 PR 已 MERGED/CLOSED + updated_at ≥14 天)。实际 dry-run 发现:

- channel-sync bot 用长寿命 open PR(`🔁 [sync] #N → beta/rc`)维护每个归档分支
- PR 状态永远是 open,PR 状态门永远不满足 → 存量清理永远不会触发
- search API 也无法可靠定位"原始 PR 是否已 close"

最终决策:**只看 commit 时间**。bot force-push 会刷新 commit date,commit ≥14 天意味着 bot 14 天未活动,可安全删除。commit <14 天仍跳过——这条规则既覆盖了 bot 持续 force-push 的活跃归档,也保留了"bot 14 天不维护即为冷归档"的运维心智。

详见 `docs/superpowers/specs/2026-08-19-channel-sync-branch-cleanup-design.md`。

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

每次运行都写 workflow summary:

| 指标 | 说明 |
|---|---|
| 扫描分支 | 命名前缀的 `channel-sync/*` 分支数 |
| 豁免保留 | 命中豁免清单的分支数 |
| 跳过(14 天内活跃) | commit <14 天的分支数 |
| 将删除 / 已删除 | 满足删除条件的分支数(dry-run 时为"将删除") |
| 失败 | 异常分支数 |

删除清单每行含分支名、head SHA 7 位、commit 日期,可一键重建。

## 误删恢复

1. 在 workflow summary 中找到被删分支的完整 SHA(7 位前缀足够定位)
2. 重建分支:

   ```bash
   git push origin <full-sha>:channel-sync/<name>
   ```

3. 不需要重建 PR(原 sync bot PR 仍在)

## 注意事项

- 本 workflow 只清理 `channel-sync/*` 归档分支,**绝不**碰 `beta` / `rc` / `release` / `develop` / `main` / `feat/*` / `fix/*` 等分支
- 不会触发 channel-sync 同步流程的任何改动
- 14 天阈值与 `stale-sync.yml` 的 `STALE_DAYS=14` 对齐
- 硬上限 500 分支(分 5 页 × 100)。超出时会有 warning,但目前远未触及

## 历史变更

- 2026-08-19: 初版引入(PR #374)。设计稿见 `docs/superpowers/specs/2026-08-19-channel-sync-branch-cleanup-design.md`。
- 2026-08-19: dry-run 修复 `pulls.list` `head=` 参数必须用 `owner:branch` 格式(PR #375)。
- 2026-08-19: 简化清理规则,去掉 PR 状态门(PR #378)。