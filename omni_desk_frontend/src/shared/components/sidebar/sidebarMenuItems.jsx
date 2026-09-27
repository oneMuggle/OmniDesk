import {
  AppstoreOutlined,
  BellOutlined,
  CalendarOutlined,
  CommentOutlined,
  EditOutlined,
  FileTextOutlined,
  HomeOutlined,
  LogoutOutlined,
  ProfileOutlined,
  ProjectOutlined,
  RobotOutlined,
  SettingOutlined,
  SolutionOutlined,
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
/**
 * 菜单项是否处于激活状态。默认精确匹配;``matchPrefix`` 为 true 时,
 * 子路由(如 /smart-assistant/apps/ragflow)也算激活。
 * @param {string} pathname
 * @param {{ to: string, matchPrefix?: boolean }} item
 * @returns {boolean}
 */
export const isMenuItemActive = (pathname, item) =>
  pathname === item.to || Boolean(item.matchPrefix && pathname.startsWith(`${item.to}/`));

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
      // S2-2 入口收敛:任务 / 应用(Dify、Ragflow、Office、文件分析)已并入智能助手的标签页,
      // 统计 / 审计 / 应用配置并入控制台「AI 管理」;旧地址自动重定向
      { to: "/smart-assistant", icon: RobotOutlined, text: "智能助手", permission: null, matchPrefix: true },
      { to: "/knowledge-base", icon: FileTextOutlined, text: "知识库", permission: null },
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
  {
    type: 'submenu',
    text: '联培生管理',
    icon: SolutionOutlined,
    // permission=null 表示所有登录用户都能看到外层入口,具体子项按角色过滤
    permission: null,
    subItems: [
      // 联培生管理员
      { to: "/joint-students/admin/students", text: "联培生列表", permission: '联培生管理员' },
      { to: "/joint-students/admin/reports", text: "月度报告审核", permission: '联培生管理员' },
      { to: "/joint-students/admin/cycles", text: "考核批次", permission: '联培生管理员' },
      { to: "/joint-students/admin/stipends", text: "补助复核", permission: '联培生管理员' },
      // 专家
      { to: "/joint-students/expert/scoring", icon: EditOutlined, text: "专家打分", permission: '考核专家组' },
      // 联培生本人 / 导师:permission 均为 null(所有登录用户可见),
      // 真实角色校验由 ProtectedRoute + 后端 PageRoute 权限承担
      { to: "/joint-students/student/reports", text: "我的月度报告", permission: null },
      { to: "/joint-students/student/stipends", text: "我的补助", permission: null },
      { to: "/joint-students/mentor/overview", text: "我的联培生", permission: null },
    ]
  },
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
