# mypy 压制登记册

> 最后更新：2026-07-14
> 维护者：Claude / 用户
> 关联 spec：`docs/superpowers/specs/2026-07-14-mypy-cleanup-design.md`

本文件追踪所有 `# type: ignore[code]` 压制点。每处压制必须在引入的同一 PR 中登记。

| 文件:行 | 错误码 | 原因 | 计划清理 PR / 触发条件 |
|---|---|---|---|
| `users/user_urls.py:5,8,9` | `[attr-defined]` | 历史遗留 ImportError：`PositionViewSet` / `UserViewSet` 在 `users.views` 中不存在（已迁出）。文件为 dead code（路由由 `users/urls.py` 提供，Django 不会触发此模块），`tests/test_url_coverage.py` 标记为 `xfail`。需业务重构时清理（删除文件 或 引入正确 ViewSet）。 | 业务重构 PR |
| (待填充) | | | |

## 维护规则

- **每加一个 `# type: ignore[code]`，必须在此文件加一行**（同一 PR 内）
- 每月审视一次"计划清理"列，对到期项目开 issue / PR
- 任何 # type: ignore 必须有 reason（一句话说明为何不修）