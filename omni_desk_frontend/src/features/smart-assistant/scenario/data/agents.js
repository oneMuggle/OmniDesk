// 智能体角色定义
// 用纯静态元数据，UI 渲染时取 name / role / avatarColor / iconName
import {
  ClusterOutlined,
  SafetyCertificateOutlined,
  NotificationOutlined,
  FileSearchOutlined,
  ReadOutlined,
  EditOutlined,
  AlertOutlined,
  ToolOutlined,
  AuditOutlined,
  BankOutlined,
  SendOutlined,
  RobotOutlined,
  ScheduleOutlined,
  CalendarOutlined,
  ProjectOutlined,
  LineChartOutlined,
  InboxOutlined,
} from '@ant-design/icons';

/**
 * @typedef {Object} AgentMeta
 * @property {string} id
 * @property {string} name        角色简称
 * @property {string} role        角色长描述
 * @property {string} avatarColor 头像底色
 * @property {keyof typeof ICON_MAP} iconName   Ant icon 名
 * @property {string} description 一句话能力说明
 */

/** @type {Record<string, AgentMeta>} */
const AGENTS = {
  // ── 出差/审批域 ─────────────────────────────
  dispatcher: {
    id: 'dispatcher',
    name: '调度 Agent',
    role: '出差调度',
    avatarColor: '#1677ff',
    iconName: 'ClusterOutlined',
    description: '查询差旅政策、检索人员、组装行程',
  },
  approver: {
    id: 'approver',
    name: '审批 Agent',
    role: '主管审批',
    avatarColor: '#fa8c16',
    iconName: 'SafetyCertificateOutlined',
    description: '校验差旅合规、生成审批单、记录审批轨迹',
  },
  notifier: {
    id: 'notifier',
    name: '通知 Agent',
    role: '消息分发',
    avatarColor: '#52c41a',
    iconName: 'NotificationOutlined',
    description: '邮件、企业 IM、推送多通道触达',
  },

  // ── 文档/知识域 ─────────────────────────────
  doc_retriever: {
    id: 'doc_retriever',
    name: '检索 Agent',
    role: '文档检索',
    avatarColor: '#722ed1',
    iconName: 'FileSearchOutlined',
    description: '在文档库/知识库中按语义定位候选',
  },
  summarizer: {
    id: 'summarizer',
    name: '摘要 Agent',
    role: '文档摘要',
    avatarColor: '#13c2c2',
    iconName: 'ReadOutlined',
    description: '抽取要点、生成结构化摘要与行动项',
  },
  writer: {
    id: 'writer',
    name: '写作 Agent',
    role: '内容撰写',
    avatarColor: '#eb2f96',
    iconName: 'EditOutlined',
    description: '按模板生成可分享的总结卡片',
  },

  // ── 设备/IoT 域 ─────────────────────────────
  monitor: {
    id: 'monitor',
    name: '监控 Agent',
    role: '传感器监控',
    avatarColor: '#f5222d',
    iconName: 'AlertOutlined',
    description: '持续观察传感器读数、识别异常事件',
  },
  diagnosis: {
    id: 'diagnosis',
    name: '诊断 Agent',
    role: '故障诊断',
    avatarColor: '#fa541c',
    iconName: 'ToolOutlined',
    description: '比对阈值、查阅手册、定位故障点',
  },

  // ── 合规/审计域 ─────────────────────────────
  auditor: {
    id: 'auditor',
    name: '审计 Agent',
    role: '日志审计',
    avatarColor: '#a0d911',
    iconName: 'AuditOutlined',
    description: '拉取审计日志、识别违规模式',
  },
  legal: {
    id: 'legal',
    name: '法务 Agent',
    role: '合规比对',
    avatarColor: '#2f54eb',
    iconName: 'BankOutlined',
    description: '对照合规制度、给出处置建议',
  },
  publisher: {
    id: 'publisher',
    name: '发布 Agent',
    role: '公告发布',
    avatarColor: '#08979c',
    iconName: 'SendOutlined',
    description: '起草公告、确认受众、触达全站',
  },

  // ── 值班/排班域 ─────────────────────────────
  scheduler: {
    id: 'scheduler',
    name: '排班 Agent',
    role: '值班排班',
    avatarColor: '#40a9ff',
    iconName: 'CalendarOutlined',
    description: '查询值班表、匹配换班人选、执行排班变更',
  },

  // ── 项目域 ──────────────────────────────────
  pm: {
    id: 'pm',
    name: '项目 Agent',
    role: '项目管理',
    avatarColor: '#f759ab',
    iconName: 'ProjectOutlined',
    description: '拉取项目列表、聚合进度与里程碑',
  },
  analyst: {
    id: 'analyst',
    name: '分析 Agent',
    role: '数据分析',
    avatarColor: '#73d13d',
    iconName: 'LineChartOutlined',
    description: '趋势分析、风险识别、数据健康度评估',
  },

  // ── 库存域 ───────────────────────────────────
  inventory: {
    id: 'inventory',
    name: '库存 Agent',
    role: '传感器库存',
    avatarColor: '#faad14',
    iconName: 'InboxOutlined',
    description: '查询传感器库存、拉取出入库记录、跟踪存量与校准',
  },

  // ── 通用 ────────────────────────────────────
  planner: {
    id: 'planner',
    name: '规划 Agent',
    role: '任务编排',
    avatarColor: '#595959',
    iconName: 'ScheduleOutlined',
    description: '把用户意图拆解为子任务并分配执行者',
  },
  coordinator: {
    id: 'coordinator',
    name: '协同 Agent',
    role: '团队协同',
    avatarColor: '#1d39c4',
    iconName: 'RobotOutlined',
    description: '串联多智能体产出、汇报最终答案',
  },
};

/** @type {Record<string, React.ComponentType>} */
const ICON_MAP = {
  ClusterOutlined,
  SafetyCertificateOutlined,
  NotificationOutlined,
  FileSearchOutlined,
  ReadOutlined,
  EditOutlined,
  AlertOutlined,
  ToolOutlined,
  AuditOutlined,
  BankOutlined,
  SendOutlined,
  RobotOutlined,
  ScheduleOutlined,
  CalendarOutlined,
  ProjectOutlined,
  LineChartOutlined,
  InboxOutlined,
};

export function getAgent(agentId) {
  return AGENTS[agentId];
}

export function getAgentIcon(agentId) {
  const a = AGENTS[agentId];
  if (!a) return RobotOutlined;
  return ICON_MAP[a.iconName] || RobotOutlined;
}

export function listAgents() {
  return Object.values(AGENTS);
}

export default AGENTS;
