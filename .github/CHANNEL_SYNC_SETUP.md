# Channel Sync 配置说明

## 概述

`channel-sync.yml` workflow 需要 `CHANNEL_SYNC_TOKEN` 才能 push 分支和创建 PR。
本文档说明如何配置该 token。

## 推荐方案：GitHub App

1. 进入仓库 Settings → Developer settings → GitHub Apps → New GitHub App
2. 名称：`omni-desk-channel-sync`
3. Homepage URL：留空或填仓库 URL
4. Webhook：取消勾选 "Active"
5. 权限（Repository permissions）：
   - Contents: Read & Write
   - Pull requests: Read & Write
   - Metadata: Read-only（默认）
6. 创建后下载私钥 (.pem)
7. 在仓库 Settings → Secrets and variables → Actions 添加：
   - `CHANNEL_SYNC_APP_ID` — App ID
   - `CHANNEL_SYNC_APP_PRIVATE_KEY` — 私钥全文（含 BEGIN/END 行）
8. 修改 workflow 的 token 引用：
   ```yaml
   token: ${{ secrets.CHANNEL_SYNC_TOKEN }}
   ```
   改为：
   ```yaml
   token: ${{ steps.generate_token.outputs.token }}
   ```
   并在第一步添加 `tibdex/github-app-token@v2` action 生成短期 token。

## 备选方案：Personal Access Token (PAT)

> ⚠️ 仅在无法配置 GitHub App 的内网环境下使用。

1. GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)
2. 生成新 token，scope 选 `repo`（完整仓库访问）
3. 设置过期时间：90 天（最长）
4. 在仓库 Settings → Secrets → Actions 添加 `CHANNEL_SYNC_TOKEN`
5. **必须在到期前轮换**

## 启用 Workflow

1. 合并 PR 后，workflow 默认自动启用（监听 `pull_request closed` 事件）
2. **首次启用建议**：开一个简单的 `fix: 触发测试` PR 并 merge 到 main,观察 Actions:
   - 验证 detect-sync 识别到 fix: commit
   - 验证 cherry-pick(beta) + cherry-pick(rc) 成功
   - 验证 sync PR 自动创建
3. **手动触发暂不支持**（v1 无 `workflow_dispatch`）;后续如需,可加 trigger + 上下文适配

## 调试

- **看不到 sync PR**：检查 PR 标题是否以 `🔁 [sync]` 开头（会跳过）
- **workflow 失败 403**：token 权限不足或过期
- **cherry-pick 冲突**：查看 PR 上传的 `conflict-<target>` artifact

## 冲突解决流程

当 channel-sync 检测到 cherry-pick 冲突时，会自动：

1. **生成冲突 artifact**（`conflict-<target>`）：
   - **始终上传**：
     - `conflict_files.txt` — 冲突文件清单
     - `file_history.md` — 冲突文件的历史改动
   - **条件上传**（仅当总大小 ≤ 5MB 时）：
     - `source.patch` / `target.patch` / `diverge.patch` — 三方 diff（base ↔ source ↔ target）
   - **> 5MB 时**：PR body 会标注「Patch 文件过大，请本地 cherry-pick 复现」；仅 `.txt` + `.md` 在 artifact 中。
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

