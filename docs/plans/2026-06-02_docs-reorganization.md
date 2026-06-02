# 文档重组计划

**日期:** 2026-06-02

## 背景与目标

项目 `docs/` 目录经过多次迭代积累了大量过时、冗余和分散的文档。需要：
1. 清理过时文档
2. 将已实现功能文档整理到技术手册和用户手册中
3. 采用"总览+分章节"结构组织文档，避免单文档过大
4. 将文档管理规范写入 CLAUDE.md 约束

## 涉及文件

- `docs/` 目录下所有文件
- `/home/fz/project/OmniDesk/CLAUDE.md`

## 技术方案

### 技术手册结构 (`docs/technical/`)
采用 `README.md`(总览目录) + `XX-topic-name.md`(分章节) + `24-implementation-records/`(实施记录归档)

### 用户手册结构 (`docs/user-manual/`)
采用 `README.md`(总览目录) + `XX-topic-name.md`(使用指南分章节)

### plans 目录
仅保留进行中/未完成计划，已完成计划归档至 `technical/24-implementation-records/`

## 实施步骤

- [x] 步骤 1：写入本计划文档
- [x] 步骤 2：删除过时/冗余文件（5个）
- [x] 步骤 3：创建技术手册总览与分章节
- [x] 步骤 4：创建用户手册总览与分章节
- [x] 步骤 5：整理 plans 目录
- [x] 步骤 6：更新 CLAUDE.md 约束

## 最终结构

### 技术手册 (`docs/technical/`)
24 个文件：README.md + 01-23 编号章节

### 用户手册 (`docs/user-manual/`)
12 个文件：README.md + 01-11 编号章节 + railway_deployment.md

### plans 目录（5个进行中）
- 2026-05-10-docker-build-deploy-fix.md
- 2026-05-11_three-level-external-integration.md
- 2026-06-02_ai-assistant-deep-design.md
- sensor_management_plan.md
- 2026-06-02_docs-reorganization.md（本文档）

## 风险评估

- LOW: 文件重命名可能导致外部链接失效（项目内部链接需同步更新）
- LOW: 合并部署文档时需确保信息不丢失
