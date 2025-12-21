import { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../../features/auth/context/AuthContext';
import {
  AppstoreOutlined,
  BellOutlined,
  BookOutlined,
  CalendarOutlined,
  CommentOutlined,
  DownOutlined,
  ExperimentOutlined,
  FileTextOutlined,
  FileWordOutlined,
  HomeOutlined,
  LeftOutlined,
  LogoutOutlined,
  MenuOutlined,
  ProfileOutlined,
  ProjectOutlined,
  RobotOutlined,
  SettingOutlined,
  SoundOutlined,
  UserOutlined,
} from '@ant-design/icons';
import complianceApi from '../../features/compliance/api/compliance';
import { Badge, Tooltip } from 'antd';

const Sidebar = ({ isMobileMenuOpen, toggleMobileMenu }) => {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [expandedSubMenu, setExpandedSubMenu] = useState({});
  const { isAuthenticated, logout, hasPermission } = useAuth();
  const location = useLocation();
  const [unreadNotificationCount, setUnreadNotificationCount] = useState(0);

  useEffect(() => {
    const fetchUnreadCount = async () => {
      try {
        const response = await complianceApi.getUnreadCount();
        setUnreadNotificationCount(response.data.unread_count);
      } catch (error) {
        console.error('Error fetching unread notification count:', error);
      }
    };

    if (isAuthenticated) {
      fetchUnreadCount();
      const interval = setInterval(fetchUnreadCount, 60000);
      return () => clearInterval(interval);
    }
  }, [isAuthenticated]);

  const menuItems = [
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
    { to: "/docs/cdepsio6", icon: FileTextOutlined, text: "文档", permission: 'admin' },
    { to: "/library", icon: BookOutlined, text: "书库", permission: 'admin' },
    { to: "/memos", icon: ProfileOutlined, text: "备忘录", permission: null },
    { to: "/communication", icon: CommentOutlined, text: "交流", permission: null },
    { to: "/sensor-management", icon: ExperimentOutlined, text: "传感器管理", permission: ["admin", "manager"] },
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

  const renderMenuItem = (item, index) => {
    if (item.type === 'button') {
      const Icon = item.icon;
      const buttonContent = (
        <div className="menu-item-content">
          <Icon className="icon" />
          {!isCollapsed && <span>{item.text}</span>}
        </div>
      );
      const button = (
        <button
          className="menu-item"
          onClick={() => {
            item.action();
            if (isMobileMenuOpen) toggleMobileMenu();
          }}
        >
          {buttonContent}
        </button>
      );

      return (
        <li key={index}>
          {isCollapsed ? (
            <Tooltip title={item.text} placement="right">
              {button}
            </Tooltip>
          ) : (
            button
          )}
        </li>
      );
    }

    if (item.type === 'submenu') {
      const Icon = item.icon;
      const isSubMenuActive = item.subItems.some(sub => location.pathname === sub.to);
      const isSubMenuExpanded = expandedSubMenu[item.text] || false;

      const subMenuHeader = (
        <div
          className={`menu-item ${isSubMenuActive ? 'active' : ''}`}
          onClick={() => setExpandedSubMenu(prev => ({ ...prev, [item.text]: !prev[item.text] }))}
        >
          <div className="menu-item-content">
            <Icon className="icon" />
            {!isCollapsed && (
              <>
                <span>{item.text}</span>
                <DownOutlined className={`submenu-arrow ${isSubMenuExpanded ? 'expanded' : ''}`} />
              </>
            )}
          </div>
        </div>
      );

      return (
        <li key={index}>
          {isCollapsed ? (
            <Tooltip title={item.text} placement="right">
              {subMenuHeader}
            </Tooltip>
          ) : (
            subMenuHeader
          )}
          {!isCollapsed && (
            <ul className={`submenu ${isSubMenuExpanded ? 'expanded' : ''}`}>
              {item.subItems
                .filter(subItem => hasPermission(subItem.permission))
                .map((subItem, subIndex) => {
                const SubIcon = subItem.icon;
                return (
                  <li key={subIndex}>
                    <Link
                      to={subItem.to}
                      className={`menu-item ${location.pathname === subItem.to ? 'active' : ''}`}
                      onClick={() => isMobileMenuOpen && toggleMobileMenu()}
                    >
                      <div className="menu-item-content">
                        {SubIcon && <SubIcon className="icon" />}
                        <span>{subItem.text}</span>
                        {subItem.badgeCount !== undefined && subItem.badgeCount > 0 && (
                          <Badge count={subItem.badgeCount} size="small" />
                        )}
                      </div>
                    </Link>
                  </li>
                );
              })}
            </ul>
          )}
        </li>
      );
    }

    const Icon = item.icon;
    const linkContent = (
      <div className="menu-item-content">
        <Icon className="icon" />
        {!isCollapsed && <span>{item.text}</span>}
      </div>
    );
    const link = (
      <Link
        to={item.to}
        className={`menu-item ${location.pathname === item.to ? 'active' : ''}`}
        onClick={() => isMobileMenuOpen && toggleMobileMenu()}
      >
        {linkContent}
      </Link>
    );

    return (
      <li key={index}>
        {isCollapsed ? (
          <Tooltip title={item.text} placement="right">
            {link}
          </Tooltip>
        ) : (
          link
        )}
      </li>
    );
  };

  return (
    <>
      <div className={`sidebar ${isMobileMenuOpen ? 'active' : ''} ${isCollapsed ? 'collapsed' : ''}`}>
        <div className="sidebar-header">
          <div className="user-info">
            {isAuthenticated ? (
              <>
                <UserOutlined className="user-icon" />
                {!isCollapsed && <span className="username">已登录</span>}
              </>
            ) : (
              !isCollapsed && <span className="login-hint">请登录</span>
            )}
          </div>
          {!isCollapsed && <h2><CalendarOutlined /> 智能办公系统</h2>}
          {isMobileMenuOpen && (
            <button className="close-menu" onClick={toggleMobileMenu}>
              &times;
            </button>
          )}
          {!isMobileMenuOpen && (
            <button
              className="collapse-toggle"
              onClick={() => setIsCollapsed(!isCollapsed)}
            >
              <LeftOutlined className={`collapse-icon ${isCollapsed ? 'rotate' : ''}`} />
            </button>
          )}
        </div>
        <nav className="sidebar-menu">
          <ul>
            {menuItems.filter(item => hasPermission(item.permission)).map(renderMenuItem)}
          </ul>
        </nav>
      </div>
      {!isMobileMenuOpen && (
        <button className="mobile-menu-toggle" onClick={toggleMobileMenu}>
          <MenuOutlined />
        </button>
      )}
    </>
  );
};

Sidebar.propTypes = {
  isMobileMenuOpen: PropTypes.bool.isRequired,
  toggleMobileMenu: PropTypes.func.isRequired,
};

export default Sidebar;
