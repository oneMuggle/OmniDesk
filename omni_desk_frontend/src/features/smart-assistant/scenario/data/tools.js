// 工具定义 + mock 结果工厂
// 每个工具都有明确的 input schema 描述和返回的模拟数据，
// 不接后端，结果纯前端静态生成。
import {
  SearchOutlined,
  FileTextOutlined,
  MailOutlined,
  MessageOutlined,
  AlertOutlined,
  ToolOutlined,
  AuditOutlined,
  SendOutlined,
  LinkOutlined,
  DatabaseOutlined,
  ApiOutlined,
  SafetyCertificateOutlined,
  UserOutlined,
  ScheduleOutlined,
  CalendarOutlined,
  ProjectOutlined,
  LineChartOutlined,
  SwapOutlined,
  FileExcelOutlined,
  FileWordOutlined,
  InboxOutlined,
} from '@ant-design/icons';

/**
 * @typedef {Object} ToolMeta
 * @property {string} id
 * @property {string} name        工具展示名
 * @property {string} category    trip / doc / device / compliance
 * @property {keyof typeof TOOL_ICON_MAP} iconName
 * @property {string} description 一句话用途
 * @property {(input: Record<string, unknown>, scenarioId: string) => unknown} mockFn
 *   输入 → 输出（纯本地 mock）
 */

/** @type {Record<string, ToolMeta>} */
const TOOLS = {
  // ── 出差 / 审批 ─────────────────────────────
  query_trip_policy: {
    id: 'query_trip_policy',
    name: '查询差旅政策',
    category: 'trip',
    iconName: 'ApiOutlined',
    description: '读出差旅制度的舱位/酒店/补贴上限',
    mockFn: () => ({
      policyVersion: 'v2026.06',
      flight: { domestic: 'economy', intl: 'business', cap: '¥4500' },
      hotel: { tier: '三星', capPerNight: '¥600' },
      allowance: { meal: '¥120/天', taxi: '实报' },
      requiresApprovalAbove: '¥3000',
    }),
  },
  list_users_by_dept: {
    id: 'list_users_by_dept',
    name: '查询部门人员',
    category: 'trip',
    iconName: 'UserOutlined',
    description: '列出某部门的人员',
    mockFn: () => ([
      { id: 'u001', name: '张博远', title: '高级工程师', dept: '研究院-算法组' },
      { id: 'u002', name: '李思雨', title: '产品经理', dept: '研究院-算法组' },
      { id: 'u003', name: '陈昊', title: '测试工程师', dept: '研究院-算法组' },
    ]),
  },
  create_trip_request: {
    id: 'create_trip_request',
    name: '创建出差申请单',
    category: 'trip',
    iconName: 'SafetyCertificateOutlined',
    description: '落出差差旅申请单到审批系统',
    mockFn: (input) => ({
      requestId: 'TR-2026-' + Math.floor(1000 + Math.random() * 9000),
      applicant: input?.applicantName || '张博远',
      destination: input?.destination || '上海',
      startDate: input?.startDate || '2026-09-02',
      endDate: input?.endDate || '2026-09-05',
      estimatedCost: '¥4,380',
      status: '待审批',
      workflow: ['直属主管', '部门负责人', '财务复核'],
    }),
  },
  send_email: {
    id: 'send_email',
    name: '发送邮件',
    category: 'trip',
    iconName: 'MailOutlined',
    description: '通过邮件通道发送',
    mockFn: (input) => ({
      channel: 'email',
      to: input?.to || ['manager@omnidesk.com'],
      subject: input?.subject || '出差审批通知',
      messageId: 'msg-' + Math.random().toString(36).slice(2, 8),
      acceptedAt: new Date().toISOString(),
    }),
  },
  send_im: {
    id: 'send_im',
    name: '发送企业 IM',
    category: 'trip',
    iconName: 'MessageOutlined',
    description: '通过 IM 即时推送',
    mockFn: (input) => ({
      channel: 'im',
      to: input?.to || ['李思雨', '陈昊'],
      messageId: 'im-' + Math.random().toString(36).slice(2, 8),
      acceptedAt: new Date().toISOString(),
    }),
  },

  // ── 文档 / 知识 ─────────────────────────────
  search_docs: {
    id: 'search_docs',
    name: '文档检索',
    category: 'doc',
    iconName: 'SearchOutlined',
    description: '在文档库中按关键词检索',
    mockFn: (input) => ({
      query: input?.query || '',
      hits: [
        { id: 'DOC-2024-018', title: '《OmniDesk 部署运维手册 v3.2》', score: 0.94, snippet: '…本节描述离线包完整性校验流程…' },
        { id: 'DOC-2025-007', title: '《2026 年度合规要点 (Q2 更新)》', score: 0.87, snippet: '…员工出差备案要求详见 4.2 节…' },
        { id: 'DOC-2026-002', title: '《AI 助手指南（试点）》', score: 0.81, snippet: '…多智能体协作场景下的工具调用…' },
      ],
    }),
  },
  fetch_doc: {
    id: 'fetch_doc',
    name: '读取文档全文',
    category: 'doc',
    iconName: 'FileTextOutlined',
    description: '拉取文档详细正文',
    mockFn: (input) => ({
      docId: input?.docId,
      title: '《OmniDesk 部署运维手册 v3.2》',
      author: '基础架构组',
      updatedAt: '2026-05-18',
      pages: 42,
      sections: ['环境准备', '离线包组装', '升级流程', '回滚预案', '健康检查'],
    }),
  },
  summarize_doc: {
    id: 'summarize_doc',
    name: '生成文档摘要',
    category: 'doc',
    iconName: 'FileTextOutlined',
    description: '抽取要点 + 行动项',
    mockFn: (input) => ({
      summary: '本文档梳理 OmniDesk 离线部署的全流程,重点强调升级前必须执行预检与备份,并给出回滚动作清单。',
      keyPoints: [
        '升级前必须执行 backup_db 且保留最近 10 份',
        'check_migrations 检测到破坏性变更时需人工复核',
        '健康检查需通过 5 个核心接口',
        '回滚动作不删除迁移历史,而是回滚镜像版本',
      ],
      actionItems: ['本周内梳理 9 月份升级窗口', '补充 §3.2 离线包签名校验步骤'],
      source: input?.docId,
    }),
  },
  create_summary_card: {
    id: 'create_summary_card',
    name: '生成摘要卡片',
    category: 'doc',
    iconName: 'FileTextOutlined',
    description: '把摘要渲染成可分享卡片',
    mockFn: () => ({
      cardId: 'CARD-' + Math.random().toString(36).slice(2, 8).toUpperCase(),
      shareUrl: 'https://omnidesk.local/s/c-' + Math.random().toString(36).slice(2, 8),
      createdAt: new Date().toISOString(),
    }),
  },
  send_share_link: {
    id: 'send_share_link',
    name: '分享摘要链接',
    category: 'doc',
    iconName: 'LinkOutlined',
    description: '把摘要卡片链接发到 IM / 邮件',
    mockFn: (input) => ({
      channel: 'im',
      to: input?.to || ['产品组全员'],
      shareUrl: input?.shareUrl,
      acceptedAt: new Date().toISOString(),
    }),
  },

  // ── 设备 / 传感器 ────────────────────────────
  list_sensors: {
    id: 'list_sensors',
    name: '列出传感器',
    category: 'device',
    iconName: 'DatabaseOutlined',
    description: '按区域或类别枚举传感器',
    mockFn: () => ([
      { id: 'SN-001', name: '冷水机组 A 温度', location: '机房-1F', status: 'online' },
      { id: 'SN-017', name: '服务器机柜 17 湿度', location: '机房-2F', status: 'warning' },
      { id: 'SN-024', name: 'UPS 输入电压', location: '配电间', status: 'online' },
      { id: 'SN-031', name: '冷通道压差', location: '机房-1F', status: 'critical' },
    ]),
  },
  check_threshold: {
    id: 'check_threshold',
    name: '检查传感器阈值',
    category: 'device',
    iconName: 'AlertOutlined',
    description: '判断读数是否越界',
    mockFn: (input) => ({
      sensorId: input?.sensorId,
      sensorName: input?.sensorName,
      reading: input?.reading,
      threshold: { warn: 12, critical: 16 },
      verdict: 'critical',
      severity: 'P0',
    }),
  },
  fetch_recent_readings: {
    id: 'fetch_recent_readings',
    name: '读取近期数据',
    category: 'device',
    iconName: 'ScheduleOutlined',
    description: '拉取近 24h 传感器读数',
    mockFn: () => ([
      { ts: '08:00', value: 7.8 },
      { ts: '10:00', value: 9.6 },
      { ts: '12:00', value: 13.4 },
      { ts: '14:00', value: 17.1 },
      { ts: '16:00', value: 18.9 },
    ]),
  },
  lookup_manual: {
    id: 'lookup_manual',
    name: '查阅维修手册',
    category: 'device',
    iconName: 'FileTextOutlined',
    description: '按设备型号查维修步骤',
    mockFn: (input) => ({
      deviceModel: input?.deviceModel || 'Liebert CRV',
      relevantSection: '4.3 冷通道压差告警处置',
      steps: [
        '1. 现场检查冷通道密封胶条',
        '2. 检查末端风机转速（额定 1200rpm）',
        '3. 测量差压变送器零点',
        '4. 必要时更换压差开关',
      ],
      parts: ['压差开关 ×1', '密封胶条 ×4'],
    }),
  },
  create_workorder: {
    id: 'create_workorder',
    name: '创建工单',
    category: 'device',
    iconName: 'ToolOutlined',
    description: '派单给维修团队',
    mockFn: (input) => ({
      workOrderId: 'WO-' + Math.floor(10000 + Math.random() * 90000),
      title: input?.title || '冷通道压差告警',
      severity: input?.severity || 'P0',
      assignee: '运维值班-甲班',
      sla: '30 分钟到场',
      createdAt: new Date().toISOString(),
    }),
  },
  notify_oncall: {
    id: 'notify_oncall',
    name: '通知值班',
    category: 'device',
    iconName: 'AlertOutlined',
    description: '电话 + 短信 + IM 三通道',
    mockFn: () => ({
      notified: ['138****1208 (电话)', '139****6611 (短信)', '企业 IM 全员'],
      dispatchedAt: new Date().toISOString(),
    }),
  },

  // ── 合规 / 审计 ─────────────────────────────
  fetch_audit_logs: {
    id: 'fetch_audit_logs',
    name: '拉取审计日志',
    category: 'compliance',
    iconName: 'AuditOutlined',
    description: '按时间段拉操作审计日志',
    mockFn: (input) => ({
      timeRange: input?.timeRange || '2026-08-20 ~ 2026-08-27',
      totalEntries: 1284,
      categories: [
        { name: '登录/登出', count: 612, flagged: 0 },
        { name: '文档导出', count: 184, flagged: 3 },
        { name: '审批操作', count: 233, flagged: 1 },
        { name: '出差备案', count: 95, flagged: 2 },
        { name: '设备操作', count: 160, flagged: 1 },
      ],
    }),
  },
  check_policy: {
    id: 'check_policy',
    name: '合规比对',
    category: 'compliance',
    iconName: 'SafetyCertificateOutlined',
    description: '把审计结果对照合规制度',
    mockFn: () => ({
      policiesChecked: 7,
      findings: [
        { id: 'F-001', severity: 'high', rule: '文档导出超 100 份需预先备案', matched: 3, status: 'unhandled' },
        { id: 'F-002', severity: 'medium', rule: '差旅超 ¥5000 需双人复核', matched: 2, status: 'auto-fixed' },
        { id: 'F-003', severity: 'low', rule: '设备操作后 5 分钟内需登记原因', matched: 1, status: 'unhandled' },
      ],
      overallVerdict: '需对 2 项 high/medium 进行公告通报',
    }),
  },
  compare_versions: {
    id: 'compare_versions',
    name: '版本对比',
    category: 'compliance',
    iconName: 'AuditOutlined',
    description: '对比新旧合规制度',
    mockFn: () => ({
      fromVersion: 'v2026.04',
      toVersion: 'v2026.06',
      addedRules: 3,
      removedRules: 1,
      modifiedRules: 5,
      diff: [
        '新增：出差超 ¥5000 必须双人复核',
        '移除：纸质审批豁免条款',
        '修改：文档导出阈值由 200 → 100',
      ],
    }),
  },
  draft_announcement: {
    id: 'draft_announcement',
    name: '起草合规公告',
    category: 'compliance',
    iconName: 'FileTextOutlined',
    description: '按模板生成公告草稿',
    mockFn: () => ({
      title: '【合规通报】关于 8 月审计问题的整改通知',
      audience: '全体员工',
      deadline: '2026-09-05',
      sections: ['背景', '问题清单', '整改要求', '联系人'],
      status: '草稿，待审批',
    }),
  },
  send_announcement: {
    id: 'send_announcement',
    name: '发布公告',
    category: 'compliance',
    iconName: 'SendOutlined',
    description: '把公告推送至全站',
    mockFn: (input) => ({
      announcementId: 'AN-' + Math.floor(10000 + Math.random() * 90000),
      title: input?.title,
      channels: ['站内信', '企业 IM', '邮件订阅'],
      recipientCount: 1247,
      publishedAt: new Date().toISOString(),
    }),
  },

  // ── 值班 / 换班 ─────────────────────────────
  query_duty_schedule: {
    id: 'query_duty_schedule',
    name: '查询值班表',
    category: 'duty',
    iconName: 'CalendarOutlined',
    description: '按日期查询主/备值班人与班次',
    mockFn: (input) => ({
      date: input?.date || '2026-08-28',
      shift: '甲班',
      timeSlot: '00:00 ~ 24:00',
      primary: { name: '张明远', phone: '138****2214', dept: '运维-甲班' },
      backup: { name: '刘畅', phone: '139****6611', dept: '运维-甲班' },
    }),
  },
  check_duty_swap: {
    id: 'check_duty_swap',
    name: '校验换班资格',
    category: 'duty',
    iconName: 'AuditOutlined',
    description: '检查换班规则与目标人选可用性',
    mockFn: (input) => ({
      applicant: input?.applicant || '张明远',
      target: {
        name: input?.target || '刘洋',
        dept: '运维-乙班',
        availability: '明日空闲',
        recentSwapCount: 1,
      },
      rule: '换班需双方 IM 确认 + 主管备案',
      eligible: true,
    }),
  },
  execute_duty_swap: {
    id: 'execute_duty_swap',
    name: '执行换班',
    category: 'duty',
    iconName: 'SwapOutlined',
    description: '生成换班单并更新值班表',
    mockFn: (input) => ({
      swapId: 'SW-2026-' + Math.floor(100 + Math.random() * 900),
      date: input?.date || '2026-08-28',
      from: input?.from || '张明远',
      to: input?.to || '刘洋',
      status: '已生效',
      approvedBy: '主管自动审批(规则引擎)',
      effectiveAt: new Date().toISOString(),
    }),
  },

  // ── 项目 / 进度 ─────────────────────────────
  list_projects: {
    id: 'list_projects',
    name: '查询项目列表',
    category: 'project',
    iconName: 'ProjectOutlined',
    description: '列出在管项目及整体进度',
    mockFn: () => ([
      { id: 'P-2026-011', name: '智慧园区二期', progress: 68, status: 'in_progress', owner: '王芳' },
      { id: 'P-2026-014', name: '数据中台升级', progress: 42, status: 'at_risk', owner: '赵磊' },
      { id: 'P-2026-017', name: 'AI 助手试点', progress: 85, status: 'in_progress', owner: '李思雨' },
    ]),
  },
  query_project_progress: {
    id: 'query_project_progress',
    name: '查询项目详情',
    category: 'project',
    iconName: 'LineChartOutlined',
    description: '拉取里程碑、燃尽与延期情况',
    mockFn: (input) => ({
      projectId: input?.projectId || 'P-2026-014',
      milestones: [
        { name: '需求冻结', done: true, finishedAt: '2026-07-20' },
        { name: '接口联调', done: false, eta: '2026-09-10' },
        { name: 'UAT 验收', done: false, eta: '2026-09-25' },
      ],
      velocity: '87%',
      delayDays: 3,
    }),
  },
  detect_project_risks: {
    id: 'detect_project_risks',
    name: '识别项目风险',
    category: 'project',
    iconName: 'AlertOutlined',
    description: '扫描进度/资源/依赖类风险',
    mockFn: () => ({
      risks: [
        { id: 'R-01', project: '数据中台升级', level: 'high', desc: '接口联调滞后 3 天,影响 UAT 窗口' },
        { id: 'R-02', project: '智慧园区二期', level: 'medium', desc: '前端人力缺口 1 人,建议 9/1 前补充' },
      ],
      scannedProjects: 3,
    }),
  },
  generate_project_report: {
    id: 'generate_project_report',
    name: '生成项目周报',
    category: 'project',
    iconName: 'FileTextOutlined',
    description: '把进度与风险汇总成可分享周报',
    mockFn: (input) => ({
      reportId: 'RPT-' + (input?.period || '2026-W35'),
      projectsCovered: 3,
      shareUrl: 'https://omnidesk.local/s/r-' + (input?.period || '2026w35').toLowerCase(),
      generatedAt: new Date().toISOString(),
    }),
  },

  // ── 传感器库存 ───────────────────────────────
  query_sensor_inventory: {
    id: 'query_sensor_inventory',
    name: '查询传感器库存',
    category: 'device',
    iconName: 'InboxOutlined',
    description: '按状态/类别/编号查询库存中的传感器',
    mockFn: (input) => ({
      filter: { status: input?.status || 'in_stock', category: input?.category || '温湿度传感器' },
      items: [
        { sensor_number: 'TH-2026-014', name: '高精度温湿度传感器', manufacturer: 'Rotronic', current_quantity: 12, location: '库房 A-03', status: '在库' },
        { sensor_number: 'TH-2026-021', name: '工业温湿度变送器', manufacturer: 'Vaisala', current_quantity: 5, location: '库房 A-05', status: '在库' },
        { sensor_number: 'PT-2026-008', name: '压差传感器', manufacturer: 'Setra', current_quantity: 3, location: '库房 B-01', status: '在库' },
      ],
      totalQuantity: 20,
    }),
  },
  get_sensor_movements: {
    id: 'get_sensor_movements',
    name: '拉取出入库记录',
    category: 'device',
    iconName: 'SwapOutlined',
    description: '拉取最近 N 天传感器出入库流水',
    mockFn: (input) => ({
      days: input?.days || 30,
      movements: [
        { date: '2026-08-20', type: '出库', sensor: 'TH-2026-014 高精度温湿度传感器', quantity: 2, destination_source: '机房-1F 部署', operator: '王建国' },
        { date: '2026-08-12', type: '入库', sensor: 'TH-2026-021 工业温湿度变送器', quantity: 5, destination_source: '采购入库 PO-2026-118', operator: '刘畅' },
        { date: '2026-08-05', type: '出库', sensor: 'PT-2026-008 压差传感器', quantity: 1, destination_source: '送检校准', operator: '王建国' },
      ],
    }),
  },
  check_calibration_status: {
    id: 'check_calibration_status',
    name: '核查校准状态',
    category: 'device',
    iconName: 'ScheduleOutlined',
    description: '按上次校准日期 + 校准周期计算到期情况',
    mockFn: () => ({
      checked: 3,
      okCount: 2,
      dueSoon: [
        { sensor_number: 'TH-2026-014', name: '高精度温湿度传感器', last_calibration_date: '2025-09-02', next_calibration_date: '2026-09-01', daysLeft: 5 },
      ],
      overdue: [],
    }),
  },

  // ── Office 文件处理 ─────────────────────────
  parse_office_file: {
    id: 'parse_office_file',
    name: '解析 Office 文件',
    category: 'office',
    iconName: 'FileExcelOutlined',
    description: '解析 xlsx/docx/pptx 结构与内容',
    mockFn: (input) => ({
      fileId: input?.fileId || 'FILE-2026-0892',
      fileName: '《8 月部门费用明细表.xlsx》',
      format: 'xlsx',
      sheets: ['汇总', '明细'],
      rows: 342,
      columns: ['部门', '费用类型', '金额', '日期'],
      size: '1.2 MB',
      parsedAt: new Date().toISOString(),
    }),
  },
  aggregate_office_data: {
    id: 'aggregate_office_data',
    name: '汇总表格数据',
    category: 'office',
    iconName: 'LineChartOutlined',
    description: '按维度聚合表格数据',
    mockFn: (input) => ({
      fileId: input?.fileId || 'FILE-2026-0892',
      groupBy: input?.groupBy || ['部门', '费用类型'],
      groups: [
        { dept: '研究院', category: '差旅', total: '¥48,200' },
        { dept: '研究院', category: '采购', total: '¥31,600' },
        { dept: '运营部', category: '差旅', total: '¥22,400' },
        { dept: '运营部', category: '办公', total: '¥9,800' },
      ],
      totalAmount: '¥186,400',
      topCategory: '差旅 (38%)',
    }),
  },
  generate_office_doc: {
    id: 'generate_office_doc',
    name: '生成 Office 文档',
    category: 'office',
    iconName: 'FileWordOutlined',
    description: '按模板生成 Word/Excel 报告',
    mockFn: (input) => ({
      docId: 'DOC-2026-' + Math.floor(100 + Math.random() * 900),
      fileName: (input?.title || '8 月费用汇总报告') + '.docx',
      format: input?.format || 'docx',
      pages: 6,
      downloadUrl: 'https://omnidesk.local/f/doc-' + Math.random().toString(36).slice(2, 8),
      generatedAt: new Date().toISOString(),
    }),
  },
};

/** @type {Record<string, React.ComponentType>} */
const TOOL_ICON_MAP = {
  SearchOutlined,
  FileTextOutlined,
  MailOutlined,
  MessageOutlined,
  AlertOutlined,
  ToolOutlined,
  AuditOutlined,
  SendOutlined,
  LinkOutlined,
  DatabaseOutlined,
  ApiOutlined,
  SafetyCertificateOutlined,
  UserOutlined,
  ScheduleOutlined,
  CalendarOutlined,
  ProjectOutlined,
  LineChartOutlined,
  SwapOutlined,
  FileExcelOutlined,
  FileWordOutlined,
  InboxOutlined,
};

export function getTool(toolId) {
  return TOOLS[toolId];
}

export function getToolIcon(toolId) {
  const t = TOOLS[toolId];
  if (!t) return ApiOutlined;
  return TOOL_ICON_MAP[t.iconName] || ApiOutlined;
}

/** 调用 mock 工具。input 是剧本 step 传入的对象。 */
export function invokeMockTool(toolId, input) {
  const t = TOOLS[toolId];
  if (!t) return { error: `unknown tool: ${toolId}` };
  try {
    return t.mockFn(input);
  } catch (err) {
    return { error: String(err) };
  }
}

export function listTools() {
  return Object.values(TOOLS);
}

export default TOOLS;
