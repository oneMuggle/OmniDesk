/**
 * 控制台「AI 管理」(S2-2)的标签清单。route 为 adminRoutePermissions 中的权限 key。
 * 原 /smart-assistant/stats、/control-panel/smart-assistant/audit、/control-panel/ai-apps 已重定向到这里。
 */
export const AI_MANAGEMENT_BASE = '/control-panel/ai';

export const AI_MANAGEMENT_TABS = Object.freeze([
  { key: 'stats', label: '使用统计', route: 'ai/stats' },
  { key: 'audit', label: 'Agent 审计', route: 'ai/audit' },
  { key: 'apps', label: 'AI 应用配置', route: 'ai/apps' },
  { key: 'staff', label: '数字员工', route: 'ai/staff' },
  { key: 'knowledge', label: '知识入库', route: 'ai/knowledge' },
  { key: 'budget', label: '预算与用量', route: 'ai/budget' },
]);
