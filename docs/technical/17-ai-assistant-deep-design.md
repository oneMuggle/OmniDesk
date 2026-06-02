# AI 助手深化设计（进行中）

> 智能助手下一阶段深化设计。

## 1. 新工具

| 工具 | 功能 | 数据源 |
|------|------|--------|
| DocumentTool | 公文/文档搜索 | documents |
| EventTool | 事件/日程/节假日 | events |
| MemoTool | 备忘录查询 | memos |
| ProjectTool | 项目进度 | projects |
| NewsTool | 新闻/通知搜索 | news |

## 2. 多轮上下文

- `intent_classifier.py` 支持多轮上下文
- `orchestrator.py` 传递历史到所有 LLM 调用

## 3. 工具结果渲染

`ToolResult.jsx` 支持 5 种新工具结果可视化。

## 4. 状态

新工具 + 多轮上下文 + ToolResult 渲染均已完成。详见 `docs/plans/2026-06-02_ai-assistant-deep-design.md`。
