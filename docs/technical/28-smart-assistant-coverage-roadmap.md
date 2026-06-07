# 智能助手覆盖率与质量路线图

> 📅 **创建时间:2026-06-06** — 配套 [16-smart-assistant.md](./16-smart-assistant.md) §5 的覆盖率补齐实施指南
>
> **目标**:将 `smart_assistant` 模块总覆盖率从 **63.25%** 提升至 **≥85%**,通过专项测试守卫 CI。

## 1. 当前覆盖率断点(2026-06-06 实测)

`pytest --cov=omni_desk_backend.smart_assistant` 运行结果(55 passed):

| 文件 | 覆盖率 | 缺行数 | 性质 |
|------|--------|--------|------|
| `views/llm_config.py` | 37% | 51/81 | LLM 多端点配置管理,核心 admin 功能 |
| `views/chat.py` | 48% | 50/97 | 核心对话入口,流式/非流式两路 |
| `views/stats.py` | 42% | 22/38 | 统计页 API |
| `tools/event_tool.py` | 32% | 19/28 | 事件/节假日工具 |
| `tools/sensor_tool.py` | 35% | 13/20 | 传感器工具 |
| `tools/document_tool.py` | 39% | 11/18 | 文档工具 |
| `tools/meeting_room_tool.py` | 33% | 18/27 | 会议室工具 |
| `tools/base.py` | 48% | 16/31 | 工具抽象基类 |
| `middleware/rate_limit.py` | 48% | 17/33 | 限流中间件 |
| `migrations/0004_llmendpoint_llmappconfig.py` | 52% | 11/23 | 数据迁移,业务关键 |

**已 100% 覆盖(无需补)**:`cache.py` / `tools/personnel_tool.py` / `tools/rag_tool.py` / `tools/schedule_tool.py` / `tools/registry.py` / `views/sessions.py` / `views/logs.py` / 5 个测试文件本身。

## 2. 覆盖路径

### 2.1 测试基础设施(优先级 P0)

**目标**:让所有 LLM 调用走 mock,避免真实网络抖动,确保测试稳定 + 快速(< 5s 全套)。

在 `omni_desk_backend/smart_assistant/tests/conftest.py` 抽取(新建文件):

| Fixture | 作用 | 实现要点 |
|---------|------|---------|
| `mock_llm_router` | 替换 `llm_service.router.get_router` | 返回固定 `(answer, usage)` 元组,支持 per-test 定制 |
| `mock_tool_registry` | 动态注册/替换工具 | `monkeypatch` `ToolRegistry._tools` 字典 |
| `mock_cache_backend` | 用 Django locmem cache 替换真实 cache | settings 切换 `CACHES["default"]` |
| `mock_celery_task` | 异步任务同步化 | `CELERY_TASK_ALWAYS_EAGER=True` |
| `sample_agent_log` | 工厂函数,生成 AgentLog 实例 | `factory_boy` 或手工 |
| `sample_smart_session` | 工厂函数,生成 SmartAssistantSession | 同上 |

### 2.2 关键路径测试补充(按文件分解,共 +63 用例)

| 文件 | 测试主题 | 新增用例 |
|------|----------|---------|
| `views/chat.py` | 流式响应中断、conversation_id 不存在、消息超长截断、turn_count 累加、conversation 重建 | +6 |
| `views/llm_config.py` | 端点 CRUD、激活端点切换、健康检查 fallback、配置缓存失效、删除激活端点边界 | +8 |
| `views/stats.py` | 时间区间过滤、按用户聚合、零样本边界、空 token 用量 | +5 |
| `views/knowledge_base.py` | 上传失败重试、删除时 Celery 任务取消、空数据集、文件类型校验 | +4 |
| `tools/event_tool.py` | 日期范围解析、节假日边界、空查询、跨年事件 | +5 |
| `tools/sensor_tool.py` | 设备 ID 不存在、离线设备、超时、批量查询 | +4 |
| `tools/document_tool.py` | 模板不存在、权限校验、关键词搜索、空结果 | +4 |
| `tools/meeting_room_tool.py` | 时间冲突、空闲查询、容量过滤、多人预约 | +5 |
| `tools/base.py` | execute 异常处理、schema 生成、参数验证 | +3 |
| `middleware/rate_limit.py` | 30/min 上限、TTL 续期、未认证放行、Redis 不可用降级 | +4 |
| `agent/orchestrator.py` | 工具链失败降级、缓存冲突、token 超限、多轮 history | +6 |
| `agent/tool_chain_planner.py` | JSON 解析失败、单工具降级为多工具、LLM 不可用 fallback | +3 |
| `agent/tool_chain_executor.py` | `$variable` 解析、依赖缺失、循环依赖检测 | +4 |
| `migrations/0004` | 数据迁移幂等性、回滚路径 | +2 |
| **合计** | | **+63** |

### 2.3 端到端测试(新增 `tests/test_e2e_smart_chat.py`)

| 场景 | 流程 | 期望 |
|------|------|------|
| 排班查询 happy path | 用户问"今天谁值班"→ ScheduleTool → LLM 回答 | 返回正确排班信息 |
| 多工具链 | 用户问"张三的排班和今日公告"→ tool_chain → 合成 | 返回合并信息 |
| 工具失败降级 | mock 工具抛异常 → orchestrator 捕获 | 通用回答,不 500 |
| 流式响应中断 | 客户端断连 | 服务端不崩溃,日志记录 |
| 缓存命中 | 相同 query 二次访问 | 第二次不走 LLM,响应时间 < 100ms |
| 限流触发 | 31 req/min | 第 31 个返回 429 |

### 2.4 慢查询守卫

任何 LLM mock 调用超过 100ms 触发 `pytest.warns(SlowQueryWarning)`(防止真实网络意外混入)。

## 3. CI 守卫策略(渐进)

### 3.1 pytest.ini 配置

```ini
[pytest]
addopts =
    --cov=omni_desk_backend
    --cov-fail-under=80
    ; 阶段 2(2026-06)完成后启用 smart_assistant 专项门槛:
    ; --cov-fail-under=85  → 先 70,稳定后 80,再 85
```

### 3.2 渐进时间表

| 周次 | 模块门槛 | 备注 |
|------|----------|------|
| W1(2026-06 第 2 周) | 70% | 临时门槛,允许旧 PR 渐进提升 |
| W2 | 80% | 接近项目基线 |
| W3+ | 85% | 完整目标,锁定 |

### 3.3 GitHub Actions 周报

新建 `.github/workflows/smart-assistant-coverage.yml`:

```yaml
name: smart_assistant_coverage_weekly
on:
  schedule:
    - cron: '7 9 * * 1'  # 每周一 9:07(避开整点)
  workflow_dispatch:

jobs:
  report:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.10'
      - run: |
          pip install -r omni_desk_backend/requirements.txt
          pytest omni_desk_backend/smart_assistant/ \
            --cov=omni_desk_backend.smart_assistant \
            --cov-report=xml:smart_assistant_coverage.xml \
            --cov-report=term-missing
      - uses: actions/upload-artifact@v4
        with:
          name: smart_assistant_coverage
          path: smart_assistant_coverage.xml
```

## 4. 测试质量保障

### 4.1 测试代码规范

- **AAA 模式**:每个测试明确 `Arrange / Act / Assert`
- **命名**:`test_<被测函数>_<场景>_<期望>`,如 `test_chat_stream_client_disconnect_returns_early`
- **不重复**:用 `parametrize` 覆盖相似场景(如多个工具的 happy path)
- **不真实依赖**:所有外部服务(Ollama/Ragflow/Redis)必须 mock

### 4.2 测试类型分布(目标)

| 类型 | 当前估计 | 目标 |
|------|----------|------|
| 单元测试 | 80% | 75% |
| 集成测试 | 15% | 20% |
| 端到端测试 | 5% | 5%(少量关键路径) |

### 4.3 失败排查 SOP

1. **先看覆盖率报告**:`htmlcov/index.html` 定位未覆盖行
2. **检查 mock**:`pytest -vv -s` 查看 mock 是否被正确调用
3. **隔离测试**:`pytest tests/test_xxx.py::test_yyy` 单跑
4. **不要 fix 测试,fix 实现**(除非测试本身有 bug)

## 5. 验收清单

- [ ] `tests/conftest.py` 抽取 6 个 fixture(mock_llm_router / mock_tool_registry / mock_cache_backend / mock_celery_task / sample_agent_log / sample_smart_session)
- [ ] 新增 63 个测试用例,目标覆盖率 ≥ 85%
- [ ] 新增 1 个 E2E 测试文件,6 个场景
- [ ] `pytest.ini` 启用 smart_assistant 专项门槛
- [ ] CI 工作流 `smart_assistant_coverage_weekly.yml` 创建并跑通
- [ ] 总测试数 55 → 130+,无回归
- [ ] 项目整体覆盖率 ≥ 80.89%(保持基线)

## 6. 不在本次范围

- 引入 mutation testing(`mutmut` / `cosmic-ray`)— 工具链成熟度评估中
- 引入 property-based testing(`hypothesis`)— 对 LLM 输出意义有限
- 引入 contract testing(`pact`)— 暂无外部消费者契约需求
