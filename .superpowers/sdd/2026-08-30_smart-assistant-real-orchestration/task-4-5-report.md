# 阶段 4–5 完成报告

## 状态

已完成阶段 4–5 的现有实现核对与预算边界补强。schema 降级、registry lint、subtask 原生 tool-calling、权限/确认边界、结果回灌、轮次上限及 pipeline 预算跳过逻辑均已覆盖；本次基于 baseline `d7e9de7da37b3c1ad00a92cc1a247220b2014858` 的实际代码差异仅新增一项预算防误报修复，保留工作树中未提交的前端改动。

## 改动文件与理由

- `omni_desk_backend/smart_assistant/agents/subtask_runner.py`
  - 在每轮 `generate_with_tools` 使用量计入 `SharedContext` 后立即检查预算。
  - 预算耗尽时抛出受控的 `token budget exhausted`，避免模型已经消耗完预算但返回文本/工具调用后被错误标记为成功。
  - 原有工具调用通过 `ToolRegistry.get_tool_for_user()`，统一经 `execute_native_tool()` 执行，因此继续遵守认证、scope、confirmation、risk 与 hook 边界。
- `omni_desk_backend/smart_assistant/tools/base.py`
  - 当前实现已提供未精确覆写工具的合法 OpenAI function schema 降级：`intent_type`、description、object/query、required query、`additionalProperties=false`。
- `omni_desk_backend/smart_assistant/tools/registry.py`
  - 当前实现已对 schema 做结构 lint，兼容降级 schema，不因 `NotImplementedError` 直接阻断全部工具，并按认证及 risk 排序。
- `omni_desk_backend/smart_assistant/tests/test_openai_tool_schemas.py`
  - 已覆盖 registry 实际注册工具数量、schema 合法性/strict 结构、降级工具及 malformed schema。
- `omni_desk_backend/smart_assistant/tests/test_subtask_runner_tools.py`
  - 已覆盖真实 tool-calling、参数校验、结果回灌、事件、confirmation、轮次上限、预算耗尽与匿名/不可用工具安全结果。

本阶段未修改 `tasks.py`、前端、任务 view、版本、部署文件或其他不在 brief 允许范围内的实现文件。`agent/tool_rounds_runner.py` 与 `agents/subtask_runner.py` 的接口/生命周期不同：前者依赖 orchestrator 的 context/fallback/meta 契约，后者返回 `SubTaskResult` 并由 pipeline 持有；因此保留既有共享的 `execute_native_tool` 核心，未复制或强行合并两套控制循环。

## 验证命令与完整结果

1. 现有相关后端测试（先于实现）：
   - 命令：`/home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest --ds=omni_desk_backend.settings.test omni_desk_backend/smart_assistant/tests/test_tools.py omni_desk_backend/smart_assistant/tests/test_tool_chain_runner.py omni_desk_backend/smart_assistant/tests/test_tool_chain_executor.py -q`
   - 结果：测试用例全部通过；命令整体因仓库默认全局 coverage fail-under=80 且该窄选集总覆盖率为 54% 退出 1。该 coverage 门槛不是测试失败。

2. 现有阶段聚焦测试：
   - 命令：`/home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest --ds=omni_desk_backend.settings.test --no-cov omni_desk_backend/smart_assistant/tests/test_openai_tool_schemas.py omni_desk_backend/smart_assistant/tests/test_subtask_runner_tools.py -q`
   - 结果：`63 passed, 1 warning in 10.24s`

3. 实现后工具与 pipeline 验证：
   - 命令：`/home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest --ds=omni_desk_backend.settings.test --no-cov omni_desk_backend/smart_assistant/tests/test_subtask_runner_tools.py omni_desk_backend/smart_assistant/tests/test_executor_pipeline.py -q`
   - 结果：`21 passed, 1 warning in 0.32s`

4. 阶段 4–5 完整聚焦测试：
   - 命令：`/home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest --ds=omni_desk_backend.settings.test --no-cov omni_desk_backend/smart_assistant/tests/test_openai_tool_schemas.py omni_desk_backend/smart_assistant/tests/test_subtask_runner_tools.py omni_desk_backend/smart_assistant/tests/test_executor_pipeline.py omni_desk_backend/smart_assistant/tests/test_tool_rounds_runner.py -q`
   - 结果：`83 passed, 1 warning in 11.85s`

5. 语法检查：
   - 命令：`/home/fz/anaconda3/envs/OmniDesk/bin/python -m py_compile omni_desk_backend/smart_assistant/agents/subtask_runner.py omni_desk_backend/smart_assistant/tools/base.py omni_desk_backend/smart_assistant/tools/registry.py`
   - 结果：通过，无输出。

6. diff 空白检查：
   - 命令：`git diff --check`
   - 结果：通过，无输出。

## Concerns

- 测试进程会输出 `SECRET_KEY not set` 的既有 warning；不影响测试结果。
- 首次窄选集命令触发全仓默认 coverage fail-under=80（54%），是选取范围过窄导致，不代表用例失败；阶段完整聚焦测试使用 `--no-cov` 并全部通过。
- 工作树原有 `/home/fz/project/OmniDesk/omni_desk_frontend/src/features/smart-assistant/api/agentTaskApi.js` 未提交改动已保留，未修改、未纳入本次提交。
