# 外部集成架构（进行中）

## 1. 概述

三层级外部集成体系，统一管理内网工具的导航、API 调用和插件扩展。

## 2. 三层架构

| 层级 | 说明 | 状态 |
|------|------|------|
| 第一层：外链集成 | GitLab/Jenkins 等统一导航入口，支持分类/图标/SSO | ✅ 已完成 |
| 第二层：功能调用集成 | RAGFlow/Dify 等带 API 调用的服务，iframe 嵌入 + API 代理 | 🔄 进行中 |
| 第三层：热插拔插件 | 用户上传自定义插件，沙箱执行，版本管理 | 🔄 进行中 |

## 3. 后端

`external_integration/` Django app：
- 模型：`ExternalLink`、`Integration`、`Plugin`
- 插件加载器：`plugin_loader.py`
- 沙箱执行：`plugin_sandbox.py`

## 4. 前端

| 模块 | 路径 |
|------|------|
| 外链 | `features/external-links/` |
| 集成中心 | `features/integration-hub/` |
| 插件市场 | `features/plugin-market/` |

详见 `docs/plans/2026-05-11_three-level-external-integration.md`。
