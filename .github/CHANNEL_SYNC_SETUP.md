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

1. 合并 PR 后，workflow 默认自动启用
2. 首次启用建议手动测试：
   ```bash
   gh workflow run channel-sync.yml
   ```
3. 在 Actions 页面查看日志

## 调试

- **看不到 sync PR**：检查 PR 标题是否以 `🔁 [sync]` 开头（会跳过）
- **workflow 失败 403**：token 权限不足或过期
- **cherry-pick 冲突**：查看 PR 上传的 `conflict-<target>` artifact