const SCENARIOS = [
  { id: 'trip-approval', title: '出差审批', userInput: '帮我安排出差审批流程', icon: 'CarOutlined' },
  { id: 'document-summary', title: '文档摘要', userInput: '帮我总结这份文档', icon: 'FileTextOutlined' },
  { id: 'compliance-scan', title: '合规扫描', userInput: '请检查最新合规风险', icon: 'AuditOutlined' },
];

export function getScenarios() { return SCENARIOS.slice(); }
export function getScenario(id) { return SCENARIOS.find((scenario) => scenario.id === id) || null; }
export default SCENARIOS;
