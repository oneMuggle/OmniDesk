# 30 发布渠道机制

## 概述

OmniDesk 从 v0.6.0 起引入 4 段式发布渠道(alpha / beta / preview / stable) + hotfix,
用于规范从开发自测到正式发布的完整流程。

## 渠道与分支映射

| 渠道 | 分支 | 适用场景 |
|---|---|---|
| alpha | `main` | 开发自测,每日构建 |
| beta | `beta` | 内测组验证 |
| preview | `rc` | release candidate,客户/领导预览 |
| stable | `release` | 正式生产 |
| hotfix | `release` | stable 已发布后的紧急修复 |

## 版本号规则

格式: `MAJOR.MINOR.PATCH[-CHANNEL.N]`,严格符合 SemVer 2.0 §9。

渠道升级示例:
- `1.2.0-alpha.5` → `1.2.0-beta.1`(序号重置)
- `1.2.0-rc.2` → `1.2.0`(去掉后缀)
- `1.2.0` → `1.2.1`(hotfix, PATCH bump)

## 镜像 tag

GHCR 镜像 `ghcr.io/onemuggle/omni-desk-{backend,frontend}`:

- `latest` 永远只指向 stable 渠道
- `v1.2.0-rc.1` / `v1.2.0-beta.3` / `v1.2.0-alpha.5` 各自独立
- PR 不打渠道 tag,仅 `sha-<short>` 用于 docker buildx 缓存

## 离线包目录命名

| 渠道 | 目录 |
|---|---|
| alpha | `omnidesk-offline-alpha-v1.2.0-alpha.5/` |
| beta | `omnidesk-offline-beta-v1.2.0-beta.1/` |
| preview | `omnidesk-offline-rc-v1.2.0-rc.1/` |
| stable | `omnidesk-offline-v1.2.0/` |
| hotfix | `omnidesk-offline-hotfix-v1.2.1/` |

## BUILD-MANIFEST.json

新增 `channel` 字段:

```json
{
  "version": "1.2.0-rc.1",
  "channel": "preview",
  "build_time": "2026-07-10T12:00:00Z",
  "git_sha": "abc1234",
  "images": { "backend": {...}, "frontend": {...} },
  "base_images": {...}
}
```

## API

`/api/system/version/` 返回:

```json
{
  "version": "1.2.0-rc.1",
  "channel": "preview",
  "build_time": "2026-07-10T12:00:00Z",
  "django_version": "4.2.x"
}
```

## 升级流程图

```
main (alpha)  ──promote──>  beta (beta)
beta          ──promote──>  rc (preview)
rc            ──promote──>  release (stable)
release       ──hotfix───>  release (stable, PATCH bump)
            同时 cherry-pick 回 main/beta/rc
```

## 禁止操作

- 渠道回退(stable → beta 不允许)
- 跨级升级(alpha → stable 跳过中间不允许)
- stable 渠道使用预发布版本号

详细实施计划见 `docs/superpowers/plans/2026-07-06-release-channels.md`。