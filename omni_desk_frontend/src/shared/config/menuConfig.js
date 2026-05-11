import {
  AppstoreOutlined,
  BellOutlined,
  CalendarOutlined,
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
  LinkOutlined,
} from '@ant-design/icons';
import { Badge } from 'antd';

/**
 * Main sidebar menu configuration.
 * Each item: { to, icon, text, permission } or { type: 'submenu', text, icon, permission, subItems }
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
      { to: "/intelligent-chat", icon: CommentOutlined, text: "智能问答", permission: null },
      { to: "/ragflow-chat", icon: ExperimentOutlined, text: "Ragflow 聊天", permission: null },
      { to: "/dify-apps", icon: RobotOutlined, text: "Dify 应用", permission: null },
      { to: "/office-assistant", icon: FileWordOutlined, text: "Office 助手", permission: null },
      { to: "/file-analysis", icon: FileTextOutlined, text: "文件分析", permission: null },
    ]
  },
  {
    type: 'submenu',
    text: '外部集成',
    icon: LinkOutlined,
    permission: null,
    subItems: [
      { to: "/external-links", text: "快捷外链", permission: null },
      { to: "/integration-hub", text: "集成中心", permission: null },
      { to: "/control-panel/external-links/manage", text: "外链管理", permission: 'admin' },
      { to: "/control-panel/integration-hub/manage", text: "集成服务管理", permission: 'admin' },
    ]
  },
  { to: "/memos", icon: ProfileOutlined, text: "备忘录", permission: null },
  { to: "/communication", icon: CommentOutlined, text: "交流", permission: null },
  { to: "/profile", icon: UserOutlined, text: "个人资料", permission: null },
  {
    type: 'submenu',
    text: '项目管理',
    icon: ProjectOutlined,
    permission: 'admin',
    subItems: [
      { to: "/projects", text: "项目列表", permission: 'admin' },
      { to: "/documents", text: "文档管理", permission: 'admin' },
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
