# Task 17: 修复集成断点 + 安全漏洞

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 scope-aware 跨模块汇总功能真正接入生产路径,修复 3 个 Critical 合并阻断问题 + 1 个安全漏洞。

**Architecture:** 修改 view/orchestrator/cache/result_synthesizer/serializer 5 个文件,补齐 plan 范围遗漏的集成层。

**Tech Stack:** Django 4.2 + DRF, Python 3.10。

## 背景:3 个 Critical + 1 个安全漏洞

最终代码评审(Task 28)发现 plan 范围(1-16)遗漏的集成层:

1. **C1 (Critical)**: `views/chat.py:41,130` 不传 user/scope → orchestrator,所有 scope 过滤死代码
2. **C2 (Critical)**: `result_synthesizer.py:332` 输出 `module_counts` (snake_case) vs `AggregatedDayCard` prop `moduleCounts` (camelCase) 不匹配
3. **C3 (Critical, NEW)**: orchestrator 实际返回 `multi_tool_chain`,但 `ToolResult.jsx:9` 检查 `aggregated_day` → AggregatedDayCard 永不被渲染
4. **C4 (Critical, NEW)**: QuickCommands 的 `personal_summary` intent 后端未注册,`serializers.py:79-80` 拒绝 `intent`/`scope` 字段
5. **P0 安全漏洞**: `cache.py:38-49` `cache_tool_result` 用 `context_sig=""` 不区分用户,scope 接入后变成 User A → User B 数据泄露

## 实施步骤

### Step 1: 修改 `views/chat.py` (line 41 + 130 注入 ToolContext)

在 `chat.py:40` 附近添加 import,line 41 + 130 改为:

```python
from smart_assistant.scope import resolve_scope
from smart_assistant.tools.tool_context import ToolContext

# line 41:
tool_context = ToolContext(user=request.user, scope=resolve_scope(request.user))
result = orchestrator.process(query, conversation_history, tool_context=tool_context)

# line 130:
tool_context = ToolContext(user=request.user, scope=resolve_scope(request.user))
for chunk in orchestrator.process_stream(query, conversation_history, tool_context=tool_context):
    yield chunk
```

### Step 2: 修改 `agent/orchestrator.py` (接受 tool_context + 调 ToolChainExecutor + ResultSynthesizer)

- `process()` / `process_stream()` 签名加 `tool_context=None`
- `_process_chain()` 把 `execute_tool_chain()` 替换为 `ToolChainExecutor().execute(plan, tool_context)`
- 多工具路径调 `ResultSynthesizer().synthesize(results, user_query)`,把 `summary + items + moduleCounts` 塞入 `result` 字段
- **关键:** 返回的 intent 字段从 `multi_tool_chain` 改为 `aggregated_day`(让 ToolResult.jsx 触发 AggregatedDayCard)

### Step 3: 修改 `cache.py` (把 user.pk + scope 加入 key,防缓存投毒)

```python
def cache_tool_result(tool_name, query, result, context_sig=""):
    key = _key("tool", tool_name, query, context_sig)
    # 现有逻辑...
```

调用方需传入 `context_sig=f"u{user.pk}_s{scope.value}"`。

### Step 4: 修改 `agent/result_synthesizer.py:332` (snake_case → camelCase)

```python
return {
    "summary": summary,
    "items": items,
    "total_count": len(items),
    "moduleCounts": module_counts,  # 改 snake_case → camelCase
}
```

同时更新 Python 测试断言从 `module_counts` 改为 `moduleCounts`。

### Step 5: 修改 `serializers.py` 接受 `intent`/`scope` (或前端翻译回 query)

**方案 A(后端):** 扩 `SmartChatRequestSerializer`:
```python
class SmartChatRequestSerializer(serializers.Serializer):
    query = serializers.CharField(...)
    conversation_id = serializers.IntegerField(...)
    intent = serializers.CharField(required=False)
    scope = serializers.CharField(required=False)
```

**方案 B(前端):** QuickCommands 把 `{intent, scope}` 翻译为 query 字符串(如 `"我的本周"` → `"这周我有哪些事"`),继续走原 `query` 路径。

**推荐方案 B**(更简单,不需要后端新增工具)。

### Step 6: 添加真实 E2E(scope-filtered 数据回归测试)

在 `test_e2e_smart_chat.py` 加一个测试:三身份 + 真实 multi-tool query + 断言 response.data 中 `moduleCounts` 字段 + summary(scope-filtered 数据真的不同)。

### Step 7: 跑测试 + 更新 coverage

- 全套 backend pytest
- 全套 frontend npm test
- Backend coverage ≥85%
- ruff + ESLint clean

### Step 8: 更新 docs(新增"集成修复"段落)

在 `docs/technical/16-smart-assistant.md` §7 增补:
- 说明 5 个修复已落地
- 更新"已知 gap"段落移除已修复项

## 验收

- [ ] Step 1-8 全部完成
- [ ] Backend coverage ≥85%
- [ ] 新增 E2E scope-filtered 测试通过
- [ ] 5 个 Critical 问题全部修复
- [ ] 缓存投毒漏洞修复
- [ ] ruff + ESLint 0 警告
- [ ] docs 更新
- [ ] 整体分支最终评审通过

## 风险

- 缓存 key 变更可能影响现有缓存(部署时清空 cache)
- orchestrator 签名扩展可能影响其他调用方
- 建议同时给 cache key 升级,部署时全量 cache flush
