import {
  AppstoreOutlined,
  BellOutlined,
  CalendarOutlined,
  ClusterOutlined,
  CommentOutlined,
  ExperimentOutlined,
  FileTextOutlined,
  FileWordOutlined,
  HomeOutlined,
  LogoutOutlined,
  ProfileOutlined,
  ProjectOutlined,
  RobotOutlined,
  SettingOutlined,
  SoundOutlined,
  UserOutlined,
} from '@ant-design/icons';

/**
 * 生成侧边栏主菜单配置。
 * 逐字搬自原 Sidebar.jsx 的 menuItems useMemo（L84-131），行为零变化。
 * 含 JSX 图标引用 → 本文件扩展名必须为 .jsx（Vite 拒绝 .js 内 JSX）。
 *
 * @param {{ logout: Function, unreadNotificationCount: number }} params
 * @returns {Array<object>} 菜单项数组（{to, icon, text, permission} | {type:'submenu',...} | {type:'button',...}）
 */
export const createMenuItems = ({ logout, unreadNotificationCount }) => [
  { to: "/", icon: HomeOutlined, text: "首页", permission: null },
  { to: "/announcements", icon: SoundOutlined, text: "公告栏", permission: null },
  {
    type: 'submenu',
    text: '日历',
    icon: CalendarOutlined,
    permission: null,
    subItems: [
      { to: "/trial-schedule", text: "试验日程", permission: null },
      { to: "/shift-schedule", text: "排班日程", permission: null },
      { to: "/meeting-rooms", text: "会议室预约", permission: null },
    ]
  },
  {
    type: 'submenu',
    text: 'AI 助手',
    icon: AppstoreOutlined,
    permission: null,
    subItems: [
      { to: "/smart-assistant", icon: RobotOutlined, text: "智能助手", permission: null },
      { to: "/smart-assistant/tasks", icon: ClusterOutlined, text: "多Agent任务", permission: null },
      { to: "/knowledge-base", icon: FileTextOutlined, text: "知识库管理", permission: null },
      { to: "/ragflow-chat", icon: ExperimentOutlined, text: "Ragflow 聊天", permission: null },
      { to: "/dify-apps", icon: RobotOutlined, text: "Dify 应用", permission: null },
      { to: "/office-assistant", icon: FileWordOutlined, text: "Office 助手", permission: null },
      { to: "/file-analysis", icon: FileTextOutlined, text: "文件分析", permission: null },
    ]
  },
  { to: "/documents-library", icon: FileTextOutlined, text: "文档库", permission: null },
  { to: "/memos", icon: ProfileOutlined, text: "备忘录", permission: null },
  { to: "/communication", icon: CommentOutlined, text: "交流", permission: null },
  { to: "/profile", icon: UserOutlined, text: "个人资料", permission: null },
  {
    type: 'submenu',
    text: '项目管理',
    icon: ProjectOutlined,
    permission: 'admin',
    subItems: [
      { to: "/control-panel/projects", text: "项目列表", permission: 'admin' },
      { to: "/control-panel/documents", text: "文档管理", permission: 'admin' },
      { to: "/control-panel/compliance", text: "合规问题", permission: 'admin' },
      { to: "/notifications", icon: BellOutlined, text: "通知中心", permission: 'admin', badgeCount: unreadNotificationCount },
    ]
  },
  {
    type: 'submenu',
    text: '外部集成',
    icon: SettingOutlined,
    permission: ['admin', 'manager'],
    subItems: [
      { to: "/external-links", text: "快捷外链", permission: ['admin', 'manager'] },
      { to: "/integration-hub", text: "集成中心", permission: ['admin', 'manager'] },
      { to: "/plugin-market", text: "插件市场", permission: ['admin', 'manager'] },
      { to: "/control-panel/external-links/manage", text: "外链管理", permission: 'admin' },
      { to: "/control-panel/integration-hub/manage", text: "集成管理", permission: 'admin' },
      { to: "/control-panel/plugin-market/manage", text: "插件管理", permission: 'admin' },
    ]
  },
  { to: "/control-panel", icon: SettingOutlined, text: "管理中心", permission: ["admin", "manager"] },
  { type: 'button', icon: LogoutOutlined, text: '退出登录', action: logout, permission: null },
];

/**
 * 生成用户下拉菜单配置。
 * 逐字搬自原 Sidebar.jsx 的 userDropdownItems useMemo（L336-360），行为零变化。
 *
 * @param {{ navigate: Function, logout: Function }} params
 * @returns {Array<object>} 下拉项数组（profile/settings/divider/logout danger）
 */
export const createUserDropdownItems = ({ navigate, logout }) => [
  {
    key: 'profile',
    icon: <UserOutlined />,
    label: '个人资料',
    onClick: () => navigate('/profile'),
  },
  {
    key: 'settings',
    icon: <SettingOutlined />,
    label: '设置',
    onClick: () => navigate('/control-panel'),
  },
  { type: 'divider' },
  {
    key: 'logout',
    icon: <LogoutOutlined />,
    label: '退出登录',
    danger: true,
    onClick: () => {
      logout();
      navigate('/login');
    },
  },
];
