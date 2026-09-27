/**
 * 智能助手统一入口(S2-2)的标签与应用清单:单一数据源。
 * 路由(routes/index.jsx)、标签栏(SmartAssistantLayout)、应用列表(AssistantAppsPage)都从这里取值。
 */

export const ASSISTANT_BASE = '/smart-assistant';

/** 顶部标签:key 用于匹配当前路由。 */
export const ASSISTANT_TABS = Object.freeze([
  { key: 'chat', label: '对话', to: ASSISTANT_BASE },
  { key: 'tasks', label: '任务', to: `${ASSISTANT_BASE}/tasks` },
  { key: 'apps', label: '应用', to: `${ASSISTANT_BASE}/apps` },
]);

/** 「应用」标签下的应用(原独立页面,旧地址见 legacyPath,会被重定向)。 */
export const ASSISTANT_APPS = Object.freeze([
  {
    key: 'dify',
    title: 'Dify 应用',
    description: '使用管理员配置的 Dify 工作流和对话应用',
    legacyPath: '/dify-apps',
  },
  {
    key: 'ragflow',
    title: 'Ragflow 聊天',
    description: '基于 Ragflow 知识库的检索问答',
    legacyPath: '/ragflow-chat',
  },
  {
    key: 'office',
    title: 'Office 助手',
    description: '生成、改写和处理 Word / Excel 文档',
    legacyPath: '/office-assistant',
  },
  {
    key: 'file-analysis',
    title: '文件分析',
    description: '上传文件，提取要点并进行问答',
    legacyPath: '/file-analysis',
  },
]);

export const appPath = (key) => `${ASSISTANT_BASE}/apps/${key}`;

/**
 * 根据当前路径返回激活的标签 key。
 * @param {string} pathname
 * @returns {'chat'|'tasks'|'apps'}
 */
export const activeAssistantTab = (pathname) => {
  if (pathname.startsWith(`${ASSISTANT_BASE}/tasks`)) return 'tasks';
  if (pathname.startsWith(`${ASSISTANT_BASE}/apps`)) return 'apps';
  return 'chat';
};
