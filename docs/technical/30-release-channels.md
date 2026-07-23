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

格式: `MAJOR.MINOR.PATCH[-CHANNEL[.N]]`,严格符合 SemVer 2.0 §9。
渠道后缀: `alpha` / `beta` / `rc` 必须带 `.N` 序号;`hotfix` 可选 `.N`(`1.2.1-hotfix` 或 `1.2.1-hotfix.1`)。

渠道升级示例:
- `1.2.0-alpha.5` → `1.2.0-beta.1`(序号重置)
- `1.2.0-rc.2` → `1.2.0`(去掉后缀)
- `1.2.0` → `1.2.1-hotfix`(hotfix, PATCH bump + 显式后缀区分 stable)

## 渠道守卫(2026-07-10 引入)

`deployment/docker/package_offline_bundle.sh` 在打包前检查"当前 git 分支 vs VERSION 推断的期望分支",不匹配时 `exit 1`。这防止在错分支上意外打包(例:在 main 上打 stable 包把未发布代码塞进 production)。

完整守卫规则 + 单元测试见 `deployment/docker/tests/test_branch_guard.sh`(20 case)。

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

## 自动同步机制(2026-07-12 引入)

`main` / `beta` / `rc` 三个渠道分支之间新增**自动同步**机制:

| 源 → 目标 | 触发条件 | 实现 |
|---|---|---|
| main → beta, rc | PR 含 `fix:` / `perf:` / `refactor:` | `.github/workflows/channel-sync.yml` |
| beta → main, rc | 同上 | 同上 |
| rc → main, beta | 同上 | 同上 |

**工作流**:

1. PR 合并到 main/beta/rc → workflow 自动开 2 个 sync PR 到其他渠道
2. Sync PR 标题前缀 `🔁 [sync] #<n> → <target>`,自动过滤防递归
3. Cherry-pick 冲突 → Sync PR 转 draft + 上传 patch + @原作者
4. 人类 review sync PR → 合并

**`release` 不参与自动同步**:

- 任何 release 修改必须走 `hotfix-v*` 流程
- 详见 [升级流程图](#升级流程图)

**配置**: 仓库需配置 `CHANNEL_SYNC_TOKEN`,详见 `.github/CHANNEL_SYNC_SETUP.md`

**设计文档**: `docs/superpowers/specs/2026-07-12-channel-fix-sync-design.md`

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

## 禁止操作

- 渠道回退(stable → beta 不允许)
- 跨级升级(alpha → stable 跳过中间不允许)
- stable 渠道使用预发布版本号

详细实施计划见 `docs/superpowers/plans/2026-07-06-release-channels.md`。