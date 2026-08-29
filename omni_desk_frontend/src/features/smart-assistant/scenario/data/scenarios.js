// 8 个预置剧本
// 每个剧本是一条 step 列表，按 delayAfter 节奏播放
import {
  CarOutlined,
  FileTextOutlined,
  AlertOutlined,
  AuditOutlined,
  TeamOutlined,
  ProjectOutlined,
  InboxOutlined,
  FileExcelOutlined,
} from '@ant-design/icons';

/**
 * @typedef {('thinking'|'tool_call'|'tool_result'|'final_answer')} StepType
 *
 * @typedef {Object} ScenarioStep
 * @property {StepType} type
 * @property {string} [agent]    thinking / tool_call / final_answer 用
 * @property {string} [tool]     tool_call 引用 tools.js 的工具 id
 * @property {string} [content]  thinking / final_answer 用
 * @property {Record<string, unknown>} [input]   tool_call 用
 * @property {unknown} [output]  tool_result 用
 * @property {string} [payloadKind]  final_answer: 'email_draft' | 'card_preview' | 'workorder' | 'announcement'
 * @property {Record<string, unknown>} [payload]  final_answer 用
 * @property {number} [delayAfter] 推进到这个 step 后等多少 ms
 *
 * @typedef {Object} Scenario
 * @property {string} id
 * @property {string} title
 * @property {string} description
 * @property {string} iconName
 * @property {string} color    ant Tag 颜色
 * @property {string[]} tags
 * @property {string[]} keywords   用于输入框匹配
 * @property {string} userInput   用户示例输入
 * @property {string[]} agents
 * @property {ScenarioStep[]} steps
 */

/** @type {Scenario[]} */
const SCENARIOS = [
  // ── 1. 出差审批 ────────────────────────────────
  {
    id: 'trip-approval',
    title: '出差审批全流程',
    description: '从申请到通知,串起差旅政策/人员/审批/IM 全链路',
    iconName: 'CarOutlined',
    color: 'blue',
    tags: ['events', 'personnel', '审批'],
    keywords: ['出差', '差旅', '审批', '报销', '请假', '行程'],
    userInput: '帮我安排 9 月初去上海出差 3 天的审批流程',
    agents: ['planner', 'dispatcher', 'approver', 'notifier'],
    steps: [
      {
        type: 'thinking',
        agent: 'planner',
        content: '用户要 9 月初 · 上海 · 3 天 · 出差审批。我将任务拆为：① 查差旅政策 ② 选申请人 ③ 创建申请单 ④ 通知审批人 + 抄送随行人员。',
        delayAfter: 900,
      },
      {
        type: 'tool_call',
        agent: 'planner',
        tool: 'query_trip_policy',
        input: {},
        delayAfter: 800,
      },
      {
        type: 'tool_result',
        tool: 'query_trip_policy',
        output: {
          policyVersion: 'v2026.06',
          flight: { domestic: 'economy', cap: '¥4500' },
          hotel: { tier: '三星', capPerNight: '¥600' },
          requiresApprovalAbove: '¥3000',
        },
        delayAfter: 600,
      },
      {
        type: 'thinking',
        agent: 'dispatcher',
        content: '上海行程预计 ¥4380,触发"≥¥3000 需主管审批"规则；继续列出同部门候选出差人。',
        delayAfter: 800,
      },
      {
        type: 'tool_call',
        agent: 'dispatcher',
        tool: 'list_users_by_dept',
        input: { dept: '研究院-算法组' },
        delayAfter: 700,
      },
      {
        type: 'tool_result',
        tool: 'list_users_by_dept',
        output: [
          { id: 'u001', name: '张博远', title: '高级工程师' },
          { id: 'u002', name: '李思雨', title: '产品经理' },
          { id: 'u003', name: '陈昊', title: '测试工程师' },
        ],
        delayAfter: 600,
      },
      {
        type: 'thinking',
        agent: 'approver',
        content: '默认委派 张博远(高级工程师) 作为申请人,匹配"高级别优先"原则；提交审批单。',
        delayAfter: 800,
      },
      {
        type: 'tool_call',
        agent: 'approver',
        tool: 'create_trip_request',
        input: {
          applicantId: 'u001',
          applicantName: '张博远',
          destination: '上海',
          startDate: '2026-09-02',
          endDate: '2026-09-05',
          estimatedCost: 4380,
        },
        delayAfter: 800,
      },
      {
        type: 'tool_result',
        tool: 'create_trip_request',
        output: {
          requestId: 'TR-2026-7421',
          applicant: '张博远',
          destination: '上海',
          status: '待审批',
          workflow: ['直属主管', '部门负责人', '财务复核'],
        },
        delayAfter: 600,
      },
      {
        type: 'thinking',
        agent: 'notifier',
        content: '审批单已生成,推送给直属主管并把副本抄送随行人员。',
        delayAfter: 800,
      },
      {
        type: 'tool_call',
        agent: 'notifier',
        tool: 'send_email',
        input: { to: ['manager@omnidesk.com'], subject: '出差审批待处理 TR-2026-7421' },
        delayAfter: 700,
      },
      {
        type: 'tool_result',
        tool: 'send_email',
        output: { channel: 'email', messageId: 'msg-9xz7q1', acceptedAt: '2026-08-27T10:23:11+08:00' },
        delayAfter: 500,
      },
      {
        type: 'tool_call',
        agent: 'notifier',
        tool: 'send_im',
        input: { to: ['李思雨', '陈昊'], text: '上海出差审批已发起,张博远将在 9/2-9/5 期间出差,请知悉并准备交接。' },
        delayAfter: 700,
      },
      {
        type: 'tool_result',
        tool: 'send_im',
        output: { channel: 'im', recipientCount: 2, messageId: 'im-4pq8rz' },
        delayAfter: 800,
      },
      {
        type: 'final_answer',
        agent: 'coordinator',
        payloadKind: 'email_draft',
        payload: {
          title: '出差申请已生成',
          fields: [
            { label: '申请单号', value: 'TR-2026-7421' },
            { label: '申请人', value: '张博远 (高级工程师)' },
            { label: '目的地', value: '上海' },
            { label: '时间', value: '2026-09-02 ~ 2026-09-05' },
            { label: '预估费用', value: '¥4,380 (触发主管审批)' },
            { label: '状态', value: '已提交,等待直属主管审批' },
          ],
          recipients: { email: ['manager@omnidesk.com'], im: ['李思雨', '陈昊'] },
        },
      },
    ],
  },

  // ── 2. 文档检索与摘要 ──────────────────────────
  {
    id: 'doc-summary',
    title: '文档检索与摘要',
    description: '在文档库中按语义搜索 → 拉取正文 → 生成可分享摘要卡片',
    iconName: 'FileTextOutlined',
    color: 'purple',
    tags: ['documents', 'knowledge'],
    keywords: ['文档', '总结', '搜索', '知识库', '摘要', '总结文档', '检索'],
    userInput: '帮我把"OmniDesk 部署运维手册"做成一份可分享的摘要',
    agents: ['doc_retriever', 'summarizer', 'writer'],
    steps: [
      {
        type: 'thinking',
        agent: 'doc_retriever',
        content: '用户要把部署运维手册做成可分享摘要；先在文档库做关键词召回。',
        delayAfter: 900,
      },
      {
        type: 'tool_call',
        agent: 'doc_retriever',
        tool: 'search_docs',
        input: { query: 'OmniDesk 部署运维 离线包 升级' },
        delayAfter: 800,
      },
      {
        type: 'tool_result',
        tool: 'search_docs',
        output: {
          hits: [
            { id: 'DOC-2024-018', title: '《OmniDesk 部署运维手册 v3.2》', score: 0.94 },
            { id: 'DOC-2025-007', title: '《2026 年度合规要点 (Q2 更新)》', score: 0.87 },
            { id: 'DOC-2026-002', title: '《AI 助手指南（试点）》', score: 0.81 },
          ],
        },
        delayAfter: 700,
      },
      {
        type: 'thinking',
        agent: 'doc_retriever',
        content: '最高分候选命中"部署运维手册 v3.2",score=0.94,直接拉全文。',
        delayAfter: 800,
      },
      {
        type: 'tool_call',
        agent: 'doc_retriever',
        tool: 'fetch_doc',
        input: { docId: 'DOC-2024-018' },
        delayAfter: 700,
      },
      {
        type: 'tool_result',
        tool: 'fetch_doc',
        output: {
          docId: 'DOC-2024-018',
          title: '《OmniDesk 部署运维手册 v3.2》',
          author: '基础架构组',
          updatedAt: '2026-05-18',
          pages: 42,
          sections: ['环境准备', '离线包组装', '升级流程', '回滚预案', '健康检查'],
        },
        delayAfter: 600,
      },
      {
        type: 'thinking',
        agent: 'summarizer',
        content: '进入摘要阶段：抽取关键点 + 行动项,与目录对照一致性。',
        delayAfter: 900,
      },
      {
        type: 'tool_call',
        agent: 'summarizer',
        tool: 'summarize_doc',
        input: { docId: 'DOC-2024-018' },
        delayAfter: 900,
      },
      {
        type: 'tool_result',
        tool: 'summarize_doc',
        output: {
          summary: '梳理 OmniDesk 离线部署全流程,重点强调升级前必须执行预检与备份,并给出回滚动作清单。',
          keyPoints: [
            '升级前必须执行 backup_db 且保留最近 10 份',
            'check_migrations 检测到破坏性变更时需人工复核',
            '健康检查需通过 5 个核心接口',
            '回滚动作不删除迁移历史,而是回滚镜像版本',
          ],
          actionItems: ['本周内梳理 9 月份升级窗口', '补充 §3.2 离线包签名校验步骤'],
        },
        delayAfter: 700,
      },
      {
        type: 'thinking',
        agent: 'writer',
        content: '把摘要写成可分享卡片,并附上源文档链接。',
        delayAfter: 800,
      },
      {
        type: 'tool_call',
        agent: 'writer',
        tool: 'create_summary_card',
        input: { docId: 'DOC-2024-018' },
        delayAfter: 700,
      },
      {
        type: 'tool_result',
        tool: 'create_summary_card',
        output: {
          cardId: 'CARD-PQ8K2X',
          shareUrl: 'https://omnidesk.local/s/c-pq8k2x',
          createdAt: '2026-08-27T10:31:12+08:00',
        },
        delayAfter: 500,
      },
      {
        type: 'tool_call',
        agent: 'writer',
        tool: 'send_share_link',
        input: { to: ['产品组全员'], shareUrl: 'https://omnidesk.local/s/c-pq8k2x' },
        delayAfter: 700,
      },
      {
        type: 'tool_result',
        tool: 'send_share_link',
        output: { channel: 'im', recipientCount: 28, acceptedAt: '2026-08-27T10:31:14+08:00' },
        delayAfter: 900,
      },
      {
        type: 'final_answer',
        agent: 'coordinator',
        payloadKind: 'card_preview',
        payload: {
          title: '《OmniDesk 部署运维手册 v3.2》摘要',
          summary: '梳理 OmniDesk 离线部署全流程,重点强调升级前必须执行预检与备份,并给出回滚动作清单。',
          keyPoints: [
            '升级前必须执行 backup_db 且保留最近 10 份',
            'check_migrations 检测到破坏性变更时需人工复核',
            '健康检查需通过 5 个核心接口',
            '回滚动作不删除迁移历史,而是回滚镜像版本',
          ],
          actionItems: ['本周内梳理 9 月份升级窗口', '补充 §3.2 离线包签名校验步骤'],
          shareUrl: 'https://omnidesk.local/s/c-pq8k2x',
          source: { id: 'DOC-2024-018', title: '部署运维手册 v3.2', pages: 42 },
        },
      },
    ],
  },

  // ── 3. 设备告警与派单 ────────────────────────
  {
    id: 'device-incident',
    title: '设备告警与派单',
    description: '传感器越界 → 查手册 → 自动派单 + 通知值班',
    iconName: 'AlertOutlined',
    color: 'red',
    tags: ['equipment', 'sensor', 'meeting-room'],
    keywords: ['设备', '故障', '传感器', '告警', '派单', '运维', '机房'],
    userInput: '机房冷通道有告警,帮我派人去处理',
    agents: ['monitor', 'diagnosis', 'dispatcher', 'notifier'],
    steps: [
      {
        type: 'thinking',
        agent: 'monitor',
        content: '持续监听发现冷通道压差越过 critical 阈值 (16 Pa),告警等级 P0。',
        delayAfter: 900,
      },
      {
        type: 'tool_call',
        agent: 'monitor',
        tool: 'list_sensors',
        input: { zone: '机房-1F' },
        delayAfter: 800,
      },
      {
        type: 'tool_result',
        tool: 'list_sensors',
        output: [
          { id: 'SN-031', name: '冷通道压差', location: '机房-1F', status: 'critical' },
        ],
        delayAfter: 600,
      },
      {
        type: 'tool_call',
        agent: 'monitor',
        tool: 'check_threshold',
        input: { sensorId: 'SN-031', sensorName: '冷通道压差', reading: 18.9 },
        delayAfter: 700,
      },
      {
        type: 'tool_result',
        tool: 'check_threshold',
        output: { verdict: 'critical', severity: 'P0', threshold: { warn: 12, critical: 16 } },
        delayAfter: 600,
      },
      {
        type: 'tool_call',
        agent: 'monitor',
        tool: 'fetch_recent_readings',
        input: { sensorId: 'SN-031', hours: 24 },
        delayAfter: 700,
      },
      {
        type: 'tool_result',
        tool: 'fetch_recent_readings',
        output: [
          { ts: '08:00', value: 7.8 },
          { ts: '10:00', value: 9.6 },
          { ts: '12:00', value: 13.4 },
          { ts: '14:00', value: 17.1 },
          { ts: '16:00', value: 18.9 },
        ],
        delayAfter: 700,
      },
      {
        type: 'thinking',
        agent: 'diagnosis',
        content: '压差呈持续上升趋势(7.8 → 18.9),高度疑似末端风机或密封胶条异常；查维修手册对应步骤。',
        delayAfter: 900,
      },
      {
        type: 'tool_call',
        agent: 'diagnosis',
        tool: 'lookup_manual',
        input: { deviceModel: 'Liebert CRV', section: '冷通道压差告警处置' },
        delayAfter: 800,
      },
      {
        type: 'tool_result',
        tool: 'lookup_manual',
        output: {
          relevantSection: '4.3 冷通道压差告警处置',
          steps: [
            '现场检查冷通道密封胶条',
            '检查末端风机转速（额定 1200rpm）',
            '测量差压变送器零点',
            '必要时更换压差开关',
          ],
          parts: ['压差开关 ×1', '密封胶条 ×4'],
        },
        delayAfter: 700,
      },
      {
        type: 'thinking',
        agent: 'dispatcher',
        content: 'P0 级告警；立即派单给运维值班甲班,并联动备件库。',
        delayAfter: 900,
      },
      {
        type: 'tool_call',
        agent: 'dispatcher',
        tool: 'create_workorder',
        input: {
          title: '机房-1F 冷通道压差告警处置',
          severity: 'P0',
          parts: ['压差开关 ×1', '密封胶条 ×4'],
        },
        delayAfter: 800,
      },
      {
        type: 'tool_result',
        tool: 'create_workorder',
        output: {
          workOrderId: 'WO-30921',
          assignee: '运维值班-甲班',
          sla: '30 分钟到场',
          createdAt: '2026-08-27T10:33:42+08:00',
        },
        delayAfter: 600,
      },
      {
        type: 'tool_call',
        agent: 'dispatcher',
        tool: 'notify_oncall',
        input: {},
        delayAfter: 700,
      },
      {
        type: 'tool_result',
        tool: 'notify_oncall',
        output: {
          notified: ['138****1208 (电话)', '139****6611 (短信)', '企业 IM 全员'],
          dispatchedAt: '2026-08-27T10:33:43+08:00',
        },
        delayAfter: 900,
      },
      {
        type: 'final_answer',
        agent: 'coordinator',
        payloadKind: 'workorder',
        payload: {
          title: '机房-1F 冷通道压差告警已派单',
          fields: [
            { label: '工单号', value: 'WO-30921' },
            { label: '严重等级', value: 'P0' },
            { label: '责任人', value: '运维值班-甲班' },
            { label: 'SLA', value: '30 分钟到场' },
            { label: '通知范围', value: '电话 + 短信 + IM' },
          ],
          readings: [
            { ts: '08:00', value: 7.8 },
            { ts: '10:00', value: 9.6 },
            { ts: '12:00', value: 13.4 },
            { ts: '14:00', value: 17.1 },
            { ts: '16:00', value: 18.9 },
          ],
          manual: {
            section: '4.3 冷通道压差告警处置',
            steps: [
              '现场检查冷通道密封胶条',
              '检查末端风机转速（额定 1200rpm）',
              '测量差压变送器零点',
              '必要时更换压差开关',
            ],
          },
        },
      },
    ],
  },

  // ── 4. 合规审计与公告 ────────────────────────
  {
    id: 'compliance-audit',
    title: '合规审计与公告',
    description: '拉审计日志 → 比对合规制度 → 起草并发布全站公告',
    iconName: 'AuditOutlined',
    color: 'gold',
    tags: ['compliance', 'news', 'communication'],
    keywords: ['合规', '审计', '通报', '公告', '合规公告', '违规'],
    userInput: '本周审计发现合规问题,起草一份面向全员的整改公告',
    agents: ['auditor', 'legal', 'publisher'],
    steps: [
      {
        type: 'thinking',
        agent: 'auditor',
        content: '从审计日志入手,聚合本周所有 flagged 操作。',
        delayAfter: 900,
      },
      {
        type: 'tool_call',
        agent: 'auditor',
        tool: 'fetch_audit_logs',
        input: { timeRange: '2026-08-20 ~ 2026-08-27' },
        delayAfter: 800,
      },
      {
        type: 'tool_result',
        tool: 'fetch_audit_logs',
        output: {
          totalEntries: 1284,
          categories: [
            { name: '登录/登出', count: 612, flagged: 0 },
            { name: '文档导出', count: 184, flagged: 3 },
            { name: '审批操作', count: 233, flagged: 1 },
            { name: '出差备案', count: 95, flagged: 2 },
            { name: '设备操作', count: 160, flagged: 1 },
          ],
        },
        delayAfter: 700,
      },
      {
        type: 'thinking',
        agent: 'legal',
        content: '对照合规制度 v2026.06；先看版本间差异,避免引述过时条款。',
        delayAfter: 900,
      },
      {
        type: 'tool_call',
        agent: 'legal',
        tool: 'compare_versions',
        input: { fromVersion: 'v2026.04', toVersion: 'v2026.06' },
        delayAfter: 800,
      },
      {
        type: 'tool_result',
        tool: 'compare_versions',
        output: {
          addedRules: 3,
          modifiedRules: 5,
          diff: [
            '新增：出差超 ¥5000 必须双人复核',
            '移除：纸质审批豁免条款',
            '修改：文档导出阈值由 200 → 100',
          ],
        },
        delayAfter: 700,
      },
      {
        type: 'tool_call',
        agent: 'legal',
        tool: 'check_policy',
        input: { version: 'v2026.06' },
        delayAfter: 900,
      },
      {
        type: 'tool_result',
        tool: 'check_policy',
        output: {
          findings: [
            { id: 'F-001', severity: 'high', rule: '文档导出超 100 份需预先备案', matched: 3 },
            { id: 'F-002', severity: 'medium', rule: '差旅超 ¥5000 需双人复核', matched: 2 },
            { id: 'F-003', severity: 'low', rule: '设备操作后 5 分钟内需登记原因', matched: 1 },
          ],
          overallVerdict: '需对 2 项 high/medium 进行公告通报',
        },
        delayAfter: 700,
      },
      {
        type: 'thinking',
        agent: 'publisher',
        content: '起草全站公告,封面用 F-001 / F-002 作为问题清单；要求 9/5 前整改。',
        delayAfter: 900,
      },
      {
        type: 'tool_call',
        agent: 'publisher',
        tool: 'draft_announcement',
        input: { findings: ['F-001', 'F-002'] },
        delayAfter: 800,
      },
      {
        type: 'tool_result',
        tool: 'draft_announcement',
        output: {
          title: '【合规通报】关于 8 月审计问题的整改通知',
          audience: '全体员工',
          deadline: '2026-09-05',
          sections: ['背景', '问题清单', '整改要求', '联系人'],
          status: '草稿，待审批',
        },
        delayAfter: 500,
      },
      {
        type: 'tool_call',
        agent: 'publisher',
        tool: 'send_announcement',
        input: { title: '【合规通报】关于 8 月审计问题的整改通知' },
        delayAfter: 800,
      },
      {
        type: 'tool_result',
        tool: 'send_announcement',
        output: {
          announcementId: 'AN-78421',
          channels: ['站内信', '企业 IM', '邮件订阅'],
          recipientCount: 1247,
          publishedAt: '2026-08-27T10:41:38+08:00',
        },
        delayAfter: 900,
      },
      {
        type: 'final_answer',
        agent: 'coordinator',
        payloadKind: 'announcement',
        payload: {
          title: '【合规通报】关于 8 月审计问题的整改通知',
          audience: '全体员工',
          deadline: '2026-09-05',
          findings: [
            { id: 'F-001', severity: 'high', rule: '文档导出超 100 份需预先备案', matched: 3 },
            { id: 'F-002', severity: 'medium', rule: '差旅超 ¥5000 需双人复核', matched: 2 },
          ],
          channels: ['站内信', '企业 IM', '邮件订阅'],
          recipientCount: 1247,
          summary: '本周审计共发现 7 项违规,其中 2 项需要通报；要求 9/5 前完成整改并提交说明。',
        },
      },
    ],
  },

  // ── 5. 值班与换班 ──────────────────────────
  {
    id: 'duty-swap',
    title: '值班查询与换班',
    description: '查值班表 → 校验换班资格 → 执行换班 → 通知相关方',
    iconName: 'TeamOutlined',
    color: 'cyan',
    tags: ['personnel', 'duty', '换班'],
    keywords: ['值班', '换班', '换', '排班', '备勤', '替班'],
    userInput: '明天谁值班？我临时有事,帮我跟刘洋换个班',
    agents: ['planner', 'scheduler', 'notifier'],
    steps: [
      {
        type: 'thinking',
        agent: 'planner',
        content: '用户明日值班,想与刘洋换班。任务拆解：① 查明日值班表 ② 校验换班资格与目标可用性 ③ 执行换班 ④ 通知双方与主管备案。',
        delayAfter: 900,
      },
      {
        type: 'tool_call',
        agent: 'scheduler',
        tool: 'query_duty_schedule',
        input: { date: '2026-08-28' },
        delayAfter: 800,
      },
      {
        type: 'tool_result',
        tool: 'query_duty_schedule',
        output: {
          date: '2026-08-28',
          shift: '甲班',
          timeSlot: '00:00 ~ 24:00',
          primary: { name: '张明远', phone: '138****2214', dept: '运维-甲班' },
          backup: { name: '刘畅', phone: '139****6611', dept: '运维-甲班' },
        },
        delayAfter: 600,
      },
      {
        type: 'thinking',
        agent: 'scheduler',
        content: '明日主值班为张明远(即用户),备值班刘畅。下一步校验换班目标刘洋的可用性与换班规则。',
        delayAfter: 800,
      },
      {
        type: 'tool_call',
        agent: 'scheduler',
        tool: 'check_duty_swap',
        input: { applicant: '张明远', target: '刘洋', date: '2026-08-28' },
        delayAfter: 700,
      },
      {
        type: 'tool_result',
        tool: 'check_duty_swap',
        output: {
          applicant: '张明远',
          target: { name: '刘洋', dept: '运维-乙班', availability: '明日空闲', recentSwapCount: 1 },
          rule: '换班需双方 IM 确认 + 主管备案',
          eligible: true,
        },
        delayAfter: 600,
      },
      {
        type: 'thinking',
        agent: 'scheduler',
        content: '刘洋明日空闲、近 30 天仅换班 1 次,符合换班条件；执行换班并生成换班单。',
        delayAfter: 800,
      },
      {
        type: 'tool_call',
        agent: 'scheduler',
        tool: 'execute_duty_swap',
        input: { date: '2026-08-28', from: '张明远', to: '刘洋' },
        delayAfter: 800,
      },
      {
        type: 'tool_result',
        tool: 'execute_duty_swap',
        output: {
          swapId: 'SW-2026-0458',
          date: '2026-08-28',
          from: '张明远',
          to: '刘洋',
          status: '已生效',
          approvedBy: '主管自动审批(规则引擎)',
          effectiveAt: '2026-08-27T15:02:11+08:00',
        },
        delayAfter: 600,
      },
      {
        type: 'thinking',
        agent: 'notifier',
        content: '换班已生效,通过 IM 通知换班双方,并邮件抄送值班邮箱备案。',
        delayAfter: 800,
      },
      {
        type: 'tool_call',
        agent: 'notifier',
        tool: 'send_im',
        input: { to: ['张明远', '刘洋'], text: '换班已确认：8/28 甲班主值班由张明远调整为刘洋,请提前 15 分钟到岗交接。' },
        delayAfter: 700,
      },
      {
        type: 'tool_result',
        tool: 'send_im',
        output: { channel: 'im', recipientCount: 2, messageId: 'im-7kq2mn' },
        delayAfter: 500,
      },
      {
        type: 'tool_call',
        agent: 'notifier',
        tool: 'send_email',
        input: { to: ['duty@omnidesk.com'], subject: '换班备案 SW-2026-0458 (2026-08-28 甲班)' },
        delayAfter: 700,
      },
      {
        type: 'tool_result',
        tool: 'send_email',
        output: { channel: 'email', messageId: 'msg-3vd8wz', acceptedAt: '2026-08-27T15:02:19+08:00' },
        delayAfter: 800,
      },
      {
        type: 'final_answer',
        agent: 'coordinator',
        payloadKind: 'email_draft',
        payload: {
          title: '换班已完成',
          fields: [
            { label: '日期', value: '2026-08-28 (周五)' },
            { label: '班次', value: '甲班 (00:00 ~ 24:00)' },
            { label: '原主值班', value: '张明远' },
            { label: '换班后主值班', value: '刘洋 (运维-乙班)' },
            { label: '换班单号', value: 'SW-2026-0458' },
            { label: '审批方式', value: '主管自动审批(规则引擎)' },
          ],
          recipients: { email: ['duty@omnidesk.com'], im: ['张明远', '刘洋'] },
        },
      },
    ],
  },

  // ── 6. 项目进度汇报 ────────────────────────
  {
    id: 'project-progress',
    title: '项目进度汇报',
    description: '聚合项目进度 → 识别风险 → 生成可分享周报',
    iconName: 'ProjectOutlined',
    color: 'geekblue',
    tags: ['projects', 'report', '风险'],
    keywords: ['项目进度', '项目', '进度', '里程碑', '周报', '交付'],
    userInput: '帮我汇总当前各项目的进展和风险',
    agents: ['planner', 'pm', 'analyst', 'writer'],
    steps: [
      {
        type: 'thinking',
        agent: 'planner',
        content: '用户要项目进展总览。拆解：① 拉项目列表 ② 查风险项目详情 ③ 风险识别 ④ 生成可分享周报。',
        delayAfter: 900,
      },
      {
        type: 'tool_call',
        agent: 'pm',
        tool: 'list_projects',
        input: {},
        delayAfter: 800,
      },
      {
        type: 'tool_result',
        tool: 'list_projects',
        output: [
          { id: 'P-2026-011', name: '智慧园区二期', progress: 68, status: 'in_progress', owner: '王芳' },
          { id: 'P-2026-014', name: '数据中台升级', progress: 42, status: 'at_risk', owner: '赵磊' },
          { id: 'P-2026-017', name: 'AI 助手试点', progress: 85, status: 'in_progress', owner: '李思雨' },
        ],
        delayAfter: 600,
      },
      {
        type: 'thinking',
        agent: 'pm',
        content: '数据中台升级处于 at_risk(42%),拉取其里程碑与延期详情。',
        delayAfter: 800,
      },
      {
        type: 'tool_call',
        agent: 'pm',
        tool: 'query_project_progress',
        input: { projectId: 'P-2026-014' },
        delayAfter: 700,
      },
      {
        type: 'tool_result',
        tool: 'query_project_progress',
        output: {
          projectId: 'P-2026-014',
          milestones: [
            { name: '需求冻结', done: true, finishedAt: '2026-07-20' },
            { name: '接口联调', done: false, eta: '2026-09-10' },
            { name: 'UAT 验收', done: false, eta: '2026-09-25' },
          ],
          velocity: '87%',
          delayDays: 3,
        },
        delayAfter: 600,
      },
      {
        type: 'thinking',
        agent: 'analyst',
        content: '接口联调未完成且已滞后 3 天,继续对全部项目做风险扫描。',
        delayAfter: 900,
      },
      {
        type: 'tool_call',
        agent: 'analyst',
        tool: 'detect_project_risks',
        input: {},
        delayAfter: 800,
      },
      {
        type: 'tool_result',
        tool: 'detect_project_risks',
        output: {
          risks: [
            { id: 'R-01', project: '数据中台升级', level: 'high', desc: '接口联调滞后 3 天,影响 UAT 窗口' },
            { id: 'R-02', project: '智慧园区二期', level: 'medium', desc: '前端人力缺口 1 人,建议 9/1 前补充' },
          ],
          scannedProjects: 3,
        },
        delayAfter: 700,
      },
      {
        type: 'thinking',
        agent: 'writer',
        content: '把进度与风险汇总成 2026-W35 周报卡片,并推送给 PMO 与项目负责人。',
        delayAfter: 900,
      },
      {
        type: 'tool_call',
        agent: 'writer',
        tool: 'generate_project_report',
        input: { period: '2026-W35' },
        delayAfter: 700,
      },
      {
        type: 'tool_result',
        tool: 'generate_project_report',
        output: {
          reportId: 'RPT-2026-W35',
          projectsCovered: 3,
          shareUrl: 'https://omnidesk.local/s/r-2026w35',
          generatedAt: '2026-08-27T15:12:44+08:00',
        },
        delayAfter: 500,
      },
      {
        type: 'tool_call',
        agent: 'writer',
        tool: 'send_share_link',
        input: { to: ['PMO 与各项目负责人'], shareUrl: 'https://omnidesk.local/s/r-2026w35' },
        delayAfter: 700,
      },
      {
        type: 'tool_result',
        tool: 'send_share_link',
        output: { channel: 'im', recipientCount: 12, acceptedAt: '2026-08-27T15:12:48+08:00' },
        delayAfter: 900,
      },
      {
        type: 'final_answer',
        agent: 'coordinator',
        payloadKind: 'card_preview',
        payload: {
          title: '项目进度周报 (2026-W35)',
          summary: '3 个在管项目中 2 个进展正常、1 个存在风险；数据中台升级滞后 3 天,需重点跟进。',
          keyPoints: [
            '智慧园区二期：68%,进展正常',
            '数据中台升级：42%,接口联调滞后 3 天 (HIGH)',
            'AI 助手试点：85%,进度超前',
          ],
          actionItems: [
            '9/1 前为智慧园区项目补充 1 名前端工程师',
            '确认数据中台接口联调新 ETA 并复核 UAT 窗口',
          ],
          shareUrl: 'https://omnidesk.local/s/r-2026w35',
          source: { id: 'RPT-2026-W35', title: '项目进度周报 2026-W35', pages: 3 },
        },
      },
    ],
  },

  // ── 7. 传感器库存查询 ──────────────────────
  {
    id: 'sensor-query',
    title: '传感器库存查询',
    description: '查询库存 → 出入库记录 → 校准状态 → 库存报告',
    iconName: 'InboxOutlined',
    color: 'green',
    tags: ['sensor', 'inventory', '查询'],
    keywords: ['传感器', '库存', '在库', '存量', '出入库', '校准', '传感器编号'],
    userInput: '查一下库存里的温湿度传感器,数量和校准状态',
    agents: ['planner', 'inventory', 'analyst'],
    steps: [
      {
        type: 'thinking',
        agent: 'planner',
        content: '用户要看在库温湿度传感器的数量与校准情况。拆解：① 查询在库传感器 ② 核对近 30 天出入库流水 ③ 核查校准到期情况 ④ 输出库存报告卡片。',
        delayAfter: 900,
      },
      {
        type: 'tool_call',
        agent: 'inventory',
        tool: 'query_sensor_inventory',
        input: { status: 'in_stock', category: '温湿度传感器' },
        delayAfter: 800,
      },
      {
        type: 'tool_result',
        tool: 'query_sensor_inventory',
        output: [
          { sensor_number: 'TH-2026-014', name: '高精度温湿度传感器', manufacturer: 'Rotronic', current_quantity: 12, location: '库房 A-03', status: '在库' },
          { sensor_number: 'TH-2026-021', name: '工业温湿度变送器', manufacturer: 'Vaisala', current_quantity: 5, location: '库房 A-05', status: '在库' },
          { sensor_number: 'PT-2026-008', name: '压差传感器', manufacturer: 'Setra', current_quantity: 3, location: '库房 B-01', status: '在库' },
        ],
        delayAfter: 600,
      },
      {
        type: 'thinking',
        agent: 'inventory',
        content: '在库 3 类传感器共 20 台。PT-2026-008 存量只有 3 台偏低,拉一下出入库流水确认动向。',
        delayAfter: 900,
      },
      {
        type: 'tool_call',
        agent: 'inventory',
        tool: 'get_sensor_movements',
        input: { days: 30 },
        delayAfter: 800,
      },
      {
        type: 'tool_result',
        tool: 'get_sensor_movements',
        output: [
          { date: '2026-08-20', type: '出库', sensor: 'TH-2026-014 高精度温湿度传感器', quantity: 2, destination_source: '机房-1F 部署', operator: '王建国' },
          { date: '2026-08-12', type: '入库', sensor: 'TH-2026-021 工业温湿度变送器', quantity: 5, destination_source: '采购入库 PO-2026-118', operator: '刘畅' },
          { date: '2026-08-05', type: '出库', sensor: 'PT-2026-008 压差传感器', quantity: 1, destination_source: '送检校准', operator: '王建国' },
        ],
        delayAfter: 600,
      },
      {
        type: 'thinking',
        agent: 'analyst',
        content: '8/5 有 1 台压差传感器送检校准尚未回库。接下来核查在库传感器的校准有效期,识别临期项。',
        delayAfter: 900,
      },
      {
        type: 'tool_call',
        agent: 'analyst',
        tool: 'check_calibration_status',
        input: { scope: 'in_stock' },
        delayAfter: 800,
      },
      {
        type: 'tool_result',
        tool: 'check_calibration_status',
        output: {
          checked: 3,
          okCount: 2,
          dueSoon: [
            { sensor_number: 'TH-2026-014', name: '高精度温湿度传感器', last_calibration_date: '2025-09-02', next_calibration_date: '2026-09-01', daysLeft: 5 },
          ],
          overdue: [],
        },
        delayAfter: 700,
      },
      {
        type: 'tool_call',
        agent: 'analyst',
        tool: 'create_summary_card',
        input: { docId: 'INV-SENSOR' },
        delayAfter: 700,
      },
      {
        type: 'tool_result',
        tool: 'create_summary_card',
        output: {
          cardId: 'CARD-INV9K2',
          shareUrl: 'https://omnidesk.local/s/c-inv9k2',
          createdAt: '2026-08-27T16:40:12+08:00',
        },
        delayAfter: 900,
      },
      {
        type: 'final_answer',
        agent: 'coordinator',
        payloadKind: 'card_preview',
        payload: {
          title: '传感器库存查询报告',
          summary: '在库传感器 3 类共 20 台；TH-2026-014 (12 台) 校准将于 9 月 1 日到期(剩 5 天),压差传感器存量 3 台偏低,建议补货。',
          keyPoints: [
            'TH-2026-014 高精度温湿度传感器 × 12 (库房 A-03, Rotronic)',
            'TH-2026-021 工业温湿度变送器 × 5 (库房 A-05, Vaisala)',
            'PT-2026-008 压差传感器 × 3 (库房 B-01, Setra),8/5 送检校准 1 台未回库',
          ],
          actionItems: [
            '9 月 1 日前安排 TH-2026-014 批次校准 (剩 5 天)',
            '跟踪送检压差传感器回库,存量建议补至安全线 5 台',
          ],
          shareUrl: 'https://omnidesk.local/s/c-inv9k2',
          source: { id: 'SENSOR-INV', title: '传感器库存 (3 类 · 20 台)', pages: 1 },
        },
      },
    ],
  },

  // ── 8. Office 文件处理 ─────────────────────
  {
    id: 'office-file',
    title: 'Office 文件处理',
    description: '解析 Excel → 汇总数据 → 生成 Word 报告 → 分发',
    iconName: 'FileExcelOutlined',
    color: 'orange',
    tags: ['office', 'documents', '报表'],
    keywords: ['office', 'excel', 'word', '表格', '解析文件', '生成报告', '文档处理'],
    userInput: '把《8 月部门费用明细表.xlsx》解析一下,生成一份汇总的 Word 报告',
    agents: ['planner', 'doc_retriever', 'analyst', 'writer', 'notifier'],
    steps: [
      {
        type: 'thinking',
        agent: 'planner',
        content: '用户要解析费用 Excel 并生成汇总 Word 报告。拆解：① 解析文件结构 ② 按维度汇总数据 ③ 按模板生成 Word ④ 分发财务与部门负责人。',
        delayAfter: 900,
      },
      {
        type: 'tool_call',
        agent: 'doc_retriever',
        tool: 'parse_office_file',
        input: { fileId: 'FILE-2026-0892' },
        delayAfter: 800,
      },
      {
        type: 'tool_result',
        tool: 'parse_office_file',
        output: {
          fileId: 'FILE-2026-0892',
          fileName: '《8 月部门费用明细表.xlsx》',
          format: 'xlsx',
          sheets: ['汇总', '明细'],
          rows: 342,
          columns: ['部门', '费用类型', '金额', '日期'],
          size: '1.2 MB',
        },
        delayAfter: 600,
      },
      {
        type: 'thinking',
        agent: 'analyst',
        content: '文件解析成功(342 行 · 2 个工作表),按"部门 × 费用类型"维度聚合。',
        delayAfter: 800,
      },
      {
        type: 'tool_call',
        agent: 'analyst',
        tool: 'aggregate_office_data',
        input: { fileId: 'FILE-2026-0892', groupBy: ['部门', '费用类型'] },
        delayAfter: 800,
      },
      {
        type: 'tool_result',
        tool: 'aggregate_office_data',
        output: {
          groupBy: ['部门', '费用类型'],
          groups: [
            { dept: '研究院', category: '差旅', total: '¥48,200' },
            { dept: '研究院', category: '采购', total: '¥31,600' },
            { dept: '运营部', category: '差旅', total: '¥22,400' },
            { dept: '运营部', category: '办公', total: '¥9,800' },
          ],
          totalAmount: '¥186,400',
          topCategory: '差旅 (38%)',
        },
        delayAfter: 700,
      },
      {
        type: 'thinking',
        agent: 'writer',
        content: '总额 ¥186,400,差旅占 38% 居首；按月度报告模板生成 Word 报告。',
        delayAfter: 900,
      },
      {
        type: 'tool_call',
        agent: 'writer',
        tool: 'generate_office_doc',
        input: { format: 'docx', template: '月度报告', title: '8 月费用汇总报告' },
        delayAfter: 800,
      },
      {
        type: 'tool_result',
        tool: 'generate_office_doc',
        output: {
          docId: 'DOC-2026-045',
          fileName: '8 月费用汇总报告.docx',
          format: 'docx',
          pages: 6,
          downloadUrl: 'https://omnidesk.local/f/doc-k3p9xm',
          generatedAt: '2026-08-27T15:28:12+08:00',
        },
        delayAfter: 600,
      },
      {
        type: 'thinking',
        agent: 'notifier',
        content: '报告已生成,邮件带附件发给财务与部门负责人,同时 IM 通知负责人群。',
        delayAfter: 800,
      },
      {
        type: 'tool_call',
        agent: 'notifier',
        tool: 'send_email',
        input: {
          to: ['finance@omnidesk.com', 'dept-heads@omnidesk.com'],
          subject: '8 月费用汇总报告(AI 助手生成)',
          attachment: '8 月费用汇总报告.docx',
        },
        delayAfter: 700,
      },
      {
        type: 'tool_result',
        tool: 'send_email',
        output: { channel: 'email', messageId: 'msg-6rt4hy', acceptedAt: '2026-08-27T15:28:20+08:00' },
        delayAfter: 500,
      },
      {
        type: 'tool_call',
        agent: 'notifier',
        tool: 'send_im',
        input: { to: ['部门负责人群'], text: '《8 月费用汇总报告》已生成并发送至各位邮箱,本月总额 ¥186,400,差旅占比 38%。' },
        delayAfter: 700,
      },
      {
        type: 'tool_result',
        tool: 'send_im',
        output: { channel: 'im', recipientCount: 18, messageId: 'im-9zb6kc' },
        delayAfter: 800,
      },
      {
        type: 'final_answer',
        agent: 'coordinator',
        payloadKind: 'email_draft',
        payload: {
          title: 'Office 文件处理完成',
          fields: [
            { label: '源文件', value: '《8 月部门费用明细表.xlsx》' },
            { label: '解析结果', value: '342 行 · 2 个工作表' },
            { label: '汇总维度', value: '部门 × 费用类型' },
            { label: '总金额', value: '¥186,400 (差旅占 38%)' },
            { label: '生成文件', value: '8 月费用汇总报告.docx (6 页)' },
            { label: '分发渠道', value: '邮件(带附件) + IM 通知' },
          ],
          recipients: {
            email: ['finance@omnidesk.com', 'dept-heads@omnidesk.com'],
            im: ['部门负责人群'],
          },
        },
      },
    ],
  },
];

const SCENARIO_ICON_MAP = {
  CarOutlined,
  FileTextOutlined,
  AlertOutlined,
  AuditOutlined,
  TeamOutlined,
  ProjectOutlined,
  InboxOutlined,
  FileExcelOutlined,
};

export function getScenario(scenarioId) {
  return SCENARIOS.find((s) => s.id === scenarioId);
}

export function getScenarioIcon(scenarioId) {
  const s = getScenario(scenarioId);
  if (!s) return FileTextOutlined;
  return SCENARIO_ICON_MAP[s.iconName] || FileTextOutlined;
}

/**
 * 在用户输入中按关键词模糊匹配；命中首个剧本即返回。
 * @param {string} input
 * @returns {Scenario | undefined}
 */
export function matchScenarioByInput(input) {
  const text = String(input || '').toLowerCase();
  if (!text) return undefined;
  let best;
  let bestScore = 0;
  for (const s of SCENARIOS) {
    let score = 0;
    for (const k of s.keywords) {
      if (text.includes(k.toLowerCase())) score += k.length;
    }
    if (score > bestScore) {
      best = s;
      bestScore = score;
    }
  }
  return best;
}

export function listScenarios() {
  return SCENARIOS;
}

export default SCENARIOS;
