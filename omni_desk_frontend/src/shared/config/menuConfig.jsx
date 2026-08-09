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
  ProfileOutlined,
  ProjectOutlined,
  RobotOutlined,
  SettingOutlined,
  SoundOutlined,
  UserOutlined,
  LogoutOutlined,
} from '@ant-design/icons';
import { Badge } from 'antd';

/**
 * 主侧边栏菜单配置 —— 单一数据源(P0-5)。
 *
 * Sidebar.jsx 通过 createMainMenuItems 生成本菜单,不再各自维护一份,
 * 避免两处定义分叉。每项形如:
 *   { to, icon, text, permission } 或 { type: 'submenu', text, icon, permission, subItems }
 *   或 { type: 'button', icon, text, action, permission }
 *
 * P0-4 死链修复:
 *   - 项目列表  /projects(无此主应用路由)→ /control-panel/projects
 *   - 文档管理  /documents(无此主应用路由)→ /control-panel/documents
 *   - 合规问题  /control-panel/compliance 已补列表页与路由(原为空白断头路由)
 */
export const createMainMenuItems = ({ logout, unreadNotificationCount }) => [
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
  { to: "/control-panel", icon: SettingOutlined, text: "管理中心", permission: ["admin", "manager"] },
  { type: 'button', icon: LogoutOutlined, text: '退出登录', action: logout, permission: null },
];

/**
 * Attach permission-checking and badge-rendering helpers to submenu items.
 */
export const enrichMenuItems = (items, hasPermission) => {
  return items.map(item => {
    if (item.type === 'submenu') {
      return {
        ...item,
        _hasPermission: hasPermission,
        _renderBadge: (count) => <Badge count={count} size="small" />,
        subItems: item.subItems?.map(sub => ({ ...sub })),
      };
    }
    return item;
  });
};
