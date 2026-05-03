import { useState, useEffect, useMemo, useCallback } from 'react';
import PropTypes from 'prop-types';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../features/auth/context/AuthContext';
import {
  AppstoreOutlined,
  BellOutlined,
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
import { Avatar, Badge, Dropdown, Tooltip, Popover } from 'antd';
import ThemeSelector from './ThemeSelector';

const STORAGE_KEY = 'sidebar_collapsed';

const Sidebar = ({ isMobileMenuOpen = false, toggleMobileMenu = () => {} }) => {
  const [isCollapsed, setIsCollapsed] = useState(() => {
    try {
      return localStorage.getItem(STORAGE_KEY) === 'true';
    } catch {
      return false;
    }
  });
  const [expandedSubMenu, setExpandedSubMenu] = useState({ '日历': true });
  const [collapsedPopoverOpen, setCollapsedPopoverOpen] = useState(null);
  const { isAuthenticated, user, logout, hasPermission } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [unreadNotificationCount, setUnreadNotificationCount] = useState(0);

  // Persist collapse state
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, String(isCollapsed));
    } catch (e) {
      console.warn('Failed to save sidebar state:', e);
    }
  }, [isCollapsed]);


  // Prevent body scroll when mobile menu is open
  useEffect(() => {
    document.body.style.overflow = isMobileMenuOpen ? 'hidden' : '';
    return () => { document.body.style.overflow = ''; };
  }, [isMobileMenuOpen]);

  // Notification polling — pause when sidebar is collapsed
  useEffect(() => {
    const fetchUnreadCount = async () => {
      try {
        const response = await complianceApi.getUnreadCount();
        setUnreadNotificationCount(response.data.unread_count);
      } catch (error) {
        console.error('Error fetching unread notification count:', error);
      }
    };

    if (isAuthenticated && !isCollapsed) {
      fetchUnreadCount();
      const interval = setInterval(fetchUnreadCount, 60000);
      return () => clearInterval(interval);
    }
  }, [isAuthenticated, isCollapsed]);

  const menuItems = useMemo(() => [
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
        { to: "/intelligent-chat", icon: CommentOutlined, text: "智能问答", permission: null },
        { to: "/ragflow-chat", icon: ExperimentOutlined, text: "Ragflow 聊天", permission: null },
        { to: "/dify-apps", icon: RobotOutlined, text: "Dify 应用", permission: null },
        { to: "/office-assistant", icon: FileWordOutlined, text: "Office 助手", permission: null },
        { to: "/file-analysis", icon: FileTextOutlined, text: "文件分析", permission: null },
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
  ], [logout, unreadNotificationCount]);

  const toggleSubMenu = useCallback((text) => {
    setExpandedSubMenu(prev => ({ ...prev, [text]: !prev[text] }));
  }, []);

  // Optimized: only location.pathname in deps, not full location object
  const renderMenuItem = useCallback((item, index) => {
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
          role="menuitem"
          onClick={() => {
            item.action();
            if (isMobileMenuOpen) toggleMobileMenu();
          }}
        >
          {buttonContent}
        </button>
      );

      return (
        <li key={index} role="none">
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
      const isSubMenuExpanded = expandedSubMenu[item.text] ?? item.subItems.some(sub => location.pathname === sub.to);

      const handleToggle = () => {
        if (isCollapsed) {
          setCollapsedPopoverOpen(prev => prev === item.text ? null : item.text);
        } else {
          toggleSubMenu(item.text);
        }
      };

      const subMenuHeader = (
        <div
          className={`menu-item ${isSubMenuActive ? 'active' : ''}`}
          role="menuitem"
          aria-expanded={isCollapsed ? undefined : isSubMenuExpanded}
          aria-haspopup={isCollapsed ? 'true' : undefined}
          tabIndex={0}
          onClick={handleToggle}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              handleToggle();
            }
          }}
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

      // Floating submenu for collapsed state
      if (isCollapsed) {
        const filteredSubItems = item.subItems.filter(subItem => hasPermission(subItem.permission));
        if (filteredSubItems.length === 0) {
          return (
            <li key={index} role="none">
              <Tooltip title={item.text} placement="right">
                {subMenuHeader}
              </Tooltip>
            </li>
          );
        }
        return (
          <li key={index} role="none">
            <Tooltip title={item.text} placement="right">
              {subMenuHeader}
            </Tooltip>
            <Popover
              open={collapsedPopoverOpen === item.text}
              placement="rightTop"
              trigger="click"
              title={null}
              content={
                <ul className="submenu popover-submenu" role="menu">
                  {filteredSubItems.map((subItem, subIndex) => {
                    const SubIcon = subItem.icon;
                    return (
                      <li key={subIndex} role="none">
                        <Link
                          to={subItem.to}
                          className={`menu-item ${location.pathname === subItem.to ? 'active' : ''}`}
                          onClick={() => {
                            setCollapsedPopoverOpen(null);
                            if (isMobileMenuOpen) toggleMobileMenu();
                          }}
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
              }
            />
          </li>
        );
      }

      // Normal expanded submenu with CSS grid animation
      return (
        <li key={index} role="none">
          {subMenuHeader}
          <ul
            className={`submenu ${isSubMenuExpanded ? 'expanded' : ''}`}
            role="menu"
          >
            {item.subItems
              .filter(subItem => hasPermission(subItem.permission))
              .map((subItem, subIndex) => {
                const SubIcon = subItem.icon;
                return (
                  <li key={subIndex} role="none">
                    <Link
                      to={subItem.to}
                      className={`menu-item ${location.pathname === subItem.to ? 'active' : ''}`}
                      role="menuitem"
                      aria-current={location.pathname === subItem.to ? 'page' : undefined}
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
        role="menuitem"
        aria-current={location.pathname === item.to ? 'page' : undefined}
        onClick={() => isMobileMenuOpen && toggleMobileMenu()}
      >
        {linkContent}
      </Link>
    );

    return (
      <li key={index} role="none">
        {isCollapsed ? (
          <Tooltip title={item.text} placement="right">
            {link}
          </Tooltip>
        ) : (
          link
        )}
      </li>
    );
  }, [collapsedPopoverOpen, isCollapsed, isMobileMenuOpen, toggleMobileMenu, location.pathname, hasPermission, expandedSubMenu, toggleSubMenu]);

  const userDropdownItems = useMemo(() => [
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
  ], [navigate, logout]);

  return (
    <>
      <div className={`sidebar ${isMobileMenuOpen ? 'active' : ''} ${isCollapsed ? 'collapsed' : ''}`}>
        <div className="sidebar-header">
          <div className="sidebar-brand">
            {!isCollapsed && (
              <>
                <div className="brand-name">OmniDesk</div>
                <div className="brand-subtitle">智能办公系统</div>
              </>
            )}
          </div>

          {isAuthenticated && !isCollapsed && (
            <Dropdown menu={{ items: userDropdownItems }} placement="bottomRight" trigger={['click']}>
              <div className="user-dropdown-trigger">
                <Avatar size="small" icon={<UserOutlined />} className="user-avatar" />
                <span className="username">{user?.username || '用户'}</span>
                <DownOutlined className="dropdown-arrow" />
              </div>
            </Dropdown>
          )}

          {isAuthenticated && !isCollapsed && <ThemeSelector />}

          {isMobileMenuOpen && (
            <button className="close-menu" onClick={toggleMobileMenu}>
              &times;
            </button>
          )}
          {!isMobileMenuOpen && (
            <button
              className="collapse-toggle"
              onClick={() => setIsCollapsed(!isCollapsed)}
              aria-label={isCollapsed ? '展开侧边栏' : '收起侧边栏'}
            >
              <LeftOutlined className={`collapse-icon ${isCollapsed ? 'rotate' : ''}`} />
            </button>
          )}
        </div>
        <nav className="sidebar-menu" role="menu" aria-label="主导航菜单">
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
  isMobileMenuOpen: PropTypes.bool,
  toggleMobileMenu: PropTypes.func,
};

export default Sidebar;
