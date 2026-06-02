# 实现计划：自动化版本发布管理系统

## 概述

创建一个 Django 管理命令 `generate_release`，用于 AI 驱动开发场景下的自动化版本发布。用户通过显式触发，系统自动分析自上次版本以来的 git 提交、按语义化版本规则确定版本号、生成 CHANGELOG.md 条目、更新 VERSION 文件，并可选择创建 git tag。

## 实施步骤

- [x] Phase 1: 创建 `git_utils.py` 工具模块 — 封装 git 操作（查找上次版本提交、获取 commit 列表、解析 Conventional Commit 格式）
- [x] Phase 2: 版本计算 + CHANGELOG 生成逻辑 — 根据提交类型自动判断 bump 级别，生成中文变更日志
- [x] Phase 3: 管理命令接口 — 支持 `--preview`、`--bump`、`--tag`、`--date` 参数，执行前预览确认
- [x] Phase 4: 单元测试 — 覆盖各类 commit 解析、版本计算、CHANGELOG 格式、边界情况
- [x] Phase 5: 文档更新 — CLAUDE.md + CHANGELOG.md 结构调整

## 新增文件

| 文件 | 说明 |
|------|------|
| `omni_desk_backend/core/git_utils.py` | Git 操作工具模块 |
| `omni_desk_backend/core/management/commands/generate_release.py` | 核心管理命令 |
| `omni_desk_backend/core/tests/test_generate_release.py` | 单元测试 |

## 修改文件

| 文件 | 说明 |
|------|------|
| `CLAUDE.md` | 添加 `generate_release` 命令说明 |
| `deployment/docker/CHANGELOG.md` | 添加使用指南注释 |

## 使用示例

```bash
# 预览（不修改任何文件）
python manage.py generate_release --preview

# 发布（自动检测版本级别）
python manage.py generate_release

# 强制指定版本级别
python manage.py generate_release --bump minor

# 发布并创建 git tag
python manage.py generate_release --tag

# 指定发布日期
python manage.py generate_release --date 2026-05-20
```

## 版本判断规则

| 提交类型 | 版本变化 | 示例 |
|---------|---------|------|
| `feat` | MINOR (0.x.0) | 0.2.0 → 0.3.0 |
| `fix` / `security` | PATCH (0.0.x) | 0.2.0 → 0.2.1 |
| `feat!` / `BREAKING CHANGE` | MAJOR (x.0.0) | 0.2.0 → 1.0.0 |
| 混合类型 | 取最高优先级 | feat + fix → MINOR |
