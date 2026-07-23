# Smart Assistant 5 个高频 E2E 场景 — 演示脚本

> **用途**:本地手动复演 5 个高频业务场景,验证 Smart Assistant 串接能力。
> **前置**:后端 `runserver` + 前端 `npm start` 已启动,Ollama 已运行(或 mock_llm_router 已注入)。
> **耗时**:约 5 分钟。

## 前置启动

```bash
# Terminal 1: 启动后端
conda run -n OmniDesk python manage.py runserver

# Terminal 2: 启动前端
cd omni_desk_frontend && npm start

# Terminal 3: 启动 Ollama(或跳过,使用 mock)
ollama serve
```

打开浏览器:`http://localhost:3000/smart-assistant`

---

## 场景 1: 排班查询

**问句**:张三这周值班是几号?

**期望回答**:列出张三本周所有值班日期。

**验证点**:
- 工具被路由到 `ScheduleTool`
- LLM 输出自然语言日期列表(非 raw 数据)
- 缓存命中时,刷新页面重复问同一句,TTFB 应 < 300ms

**手动操作**:
1. 在聊天框输入"张三这周值班是几号?" → 发送
2. 观察加载指示 + 流式打字效果
3. 查看工具卡片(应展示 schedule_card)
4. **再发一次相同问题**,观察 TTFB(应明显更快)

## 场景 2: 人员查询

**问句**:帮我找开发部的李四

**期望回答**:返回李四基本信息(部门、岗位),不返回手机号等敏感字段。

**验证点**:
- 工具被路由到 `PersonnelTool`
- 工具卡片只显示公开字段
- 跨部门查询应被工具层拒绝

**手动操作**:
1. 发送"帮我找开发部的李四"
2. 查看 tool_result(用浏览器 DevTools Network → /api/smart-assistant/chat/ → response)
3. 确认 tool_result 中无 phone/email 字段

## 场景 3: 知识库问答

**问句**:公司的 VPN 怎么登录?

**期望回答**:返回 VPN 登录步骤 + 引用来源(文档名)。

**验证点**:
- 工具被路由到 `RAGTool`
- answer 末尾或 tool_result 包含 `sources` 字段,标注文档名
- RAGFlow 不可达时,降级为通用回答 + 顶部 Banner

**手动操作**:
1. 发送"公司的 VPN 怎么登录?"
2. 验证 answer 含 VPN 步骤
3. 验证 tool_result.sources 含文档名(如 "IT操作手册.pdf")

## 场景 4: 公告查询

**问句**:这周有什么公告?

**期望回答**:列出本周所有公告标题 + 链接。

**验证点**:
- 工具被路由到 `AnnouncementTool`
- 工具卡片展示 announcement_card(标题列表)
- 时间窗口过滤:本周外的公告不应出现

**手动操作**:
1. 发送"这周有什么公告?"
2. 查看 tool_result(应只含本周日期的 Post)
3. 点击工具卡片中任一公告(若有链接)

## 场景 5: 合规检查

**问句**:张三还有几条待整改?

**期望回答**:返回张三待处理的 ComplianceIssue 数量 + 简表。

**验证点**:
- 工具被路由到 `ComplianceTool`
- 仅返回 status='pending' 的合规问题
- 普通员工只能查自己,管理员可查全部

**手动操作**:
1. 发送"张三还有几条待整改?"
2. 验证 tool_result 含 status='pending' 的 issue
3. 用普通员工账户登录再问一次,验证仅返回自己的问题

---

## 性能验证

| 指标 | 目标 | 验证方法 |
|---|---|---|
| 缓存命中 TTFB | < 300ms | DevTools Network → 重复同问句 → 看 timing |
| 流式首字节 | < 800ms(未命中)/ < 300ms(命中) | DevTools Network → 首字节时间 |
| E2E 总耗时 | < 3s/场景 | 从发送 → 收到完整 answer |

## 取消功能验证

1. 发送一个复杂问题(LLM 需 5+ 秒回答)
2. 在加载中点击"停止"按钮
3. 验证:UI 立即停止流式渲染,显示"已取消"
4. 可继续发新问题

## 截图与录屏

每个场景截图一张,文件名格式:`sa-scenario-{N}-{描述}.png`。
录屏可选,但建议保留作为文档资产。
