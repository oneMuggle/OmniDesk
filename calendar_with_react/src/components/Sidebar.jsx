import React, { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import {
  faCalendarAlt,
  faHome,
  faCog,
  faBars,
  faBell,
  faUser,
  faSignOutAlt,
  faTasks,
  faChevronLeft,
  faSignInAlt,
  faFileWord,
  faBullhorn,
  faCommentDots,
  faFlask,
  faUsers,
  faFileAlt,
  faBook, // 新增图标
  faChevronDown, // 新增图标
  faClipboardList, // 新增备忘录图标
  faRobot // 新增 Dify 应用图标
} from '@fortawesome/free-solid-svg-icons';
 
const Sidebar = ({ isMobileMenuOpen, toggleMobileMenu }) => {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [expandedSubMenu, setExpandedSubMenu] = useState({}); // 维护每个子菜单的展开状态
  const { user, isAuthenticated, logout, hasPermission } = useAuth();
  const location = useLocation();

  const menuItems = [
    { to: "/", icon: faHome, text: "首页", permission: null },
    { to: "/announcements", icon: faBullhorn, text: "公告栏", permission: null },
    {
      type: 'submenu',
      text: '日历',
      icon: faCalendarAlt,
      permission: null,
      subItems: [
        { to: "/trial-calendar", text: "试验日历", permission: null },
        { to: "/shift-calendar", text: "排班日历", permission: null },
      ]
    },
    { to: "/intelligent-chat", icon: faCommentDots, text: "智能问答", permission: null },
    { to: "/ragflow-chat", icon: faFlask, text: "Ragflow 聊天", permission: null },
    { to: "/docs/cdepsio6", icon: faFileAlt, text: "文档", permission: null },
    { to: "/file-analysis", icon: faFileAlt, text: "文件分析", permission: null },
    { to: "/library", icon: faBook, text: "书库", permission: null },
    { to: "/memos", icon: faClipboardList, text: "备忘录", permission: null }, // 备忘录链接
    { to: "/dify-apps", icon: faRobot, text: "Dify 应用", permission: null }, // 新增 Dify 应用链接
    { to: "/office-assistant", icon: faFileWord, text: "Office 助手", permission: null },
    { to: "/profile", icon: faUser, text: "个人资料", permission: null },
    {
      type: 'submenu',
      text: '项目管理',
      icon: faTasks,
      permission: ["admin", "manager"],
      subItems: [
        { to: "/projects", text: "项目列表", permission: ["admin", "manager"] },
        { to: "/documents", text: "文档管理", permission: ["admin", "manager"] },
        { to: "/admin/compliance", text: "合规问题", permission: ["admin", "manager"] },
      ]
    },
    { to: "/admin", icon: faCog, text: "管理中心", permission: ["admin", "manager"] },
    { to: "/notifications", icon: faBell, text: "通知中心", permission: null }, // 新增通知中心链接
    { type: 'button', icon: faSignOutAlt, text: '退出登录', action: logout, permission: 'authenticated' }
  ];

  const renderMenuItem = (item, index) => {
    // 权限检查
    // 移除对 /admin/schedules 和 /admin/personnel 的特殊处理，这些路由的权限将由 AdminLayout 内部处理
    if (item.permission !== null) {
      if (item.permission === 'authenticated' && !isAuthenticated) return null;
      if (Array.isArray(item.permission)) {
        if (!isAuthenticated || !item.permission.some(role => user?.role === role)) return null;
      } else if (!isAuthenticated || user?.role !== item.permission) {
        // 如果是单个权限字符串，并且用户没有该权限，则不显示
        if (!hasPermission(item.permission)) return null;
      }
    }

    if (item.type === 'button') {
      return (
        <li key={index}>
          <button
            className="menu-item"
            onClick={() => {
              item.action();
              if (isMobileMenuOpen) toggleMobileMenu();
            }}
            title={isCollapsed ? item.text : ''}
          >
            <div className="menu-item-content">
              <FontAwesomeIcon icon={item.icon} className="icon" />
              {!isCollapsed && <span>{item.text}</span>}
            </div>
          </button>
        </li>
      );
    }

    if (item.type === 'submenu') {
      const isSubMenuActive = item.subItems.some(sub => location.pathname === sub.to);
      const isSubMenuExpanded = expandedSubMenu[item.text] || false; // 根据 item.text 获取状态

      return (
        <li key={index}>
          <div
            className={`menu-item ${isSubMenuActive ? 'active' : ''}`}
            onClick={() => setExpandedSubMenu(prev => ({ ...prev, [item.text]: !prev[item.text] }))} // 切换当前子菜单的状态
            title={isCollapsed ? item.text : ''}
          >
            <div className="menu-item-content">
              <FontAwesomeIcon icon={item.icon} className="icon" />
              {!isCollapsed && (
                <>
                  <span>{item.text}</span>
                  <FontAwesomeIcon icon={faChevronDown} className={`submenu-arrow ${isSubMenuExpanded ? 'expanded' : ''}`} />
                </>
              )}
            </div>
          </div>
          {isSubMenuExpanded && !isCollapsed && ( // 根据当前子菜单的状态判断是否显示
            <ul className="submenu">
              {item.subItems.map((subItem, subIndex) => (
                <li key={subIndex}>
                  <Link
                    to={subItem.to}
                    className={`menu-item ${location.pathname === subItem.to ? 'active' : ''}`}
                    onClick={() => isMobileMenuOpen && toggleMobileMenu()}
                  >
                    <div className="menu-item-content">
                      <span>{subItem.text}</span>
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </li>
      );
    }

    return (
      <li key={index}>
        <Link
          to={item.to}
          className={`menu-item ${location.pathname === item.to ? 'active' : ''}`}
          onClick={() => isMobileMenuOpen && toggleMobileMenu()}
          title={isCollapsed ? item.text : ''}
        >
          <div className="menu-item-content">
            <FontAwesomeIcon icon={item.icon} className="icon" />
            {!isCollapsed && <span>{item.text}</span>}
          </div>
        </Link>
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
                <FontAwesomeIcon icon={faUser} className="user-icon" />
                <span className="username">已登录</span>
              </>
            ) : (
              <span className="login-hint">请登录</span>
            )}
          </div>
          <h2><FontAwesomeIcon icon={faCalendarAlt} /> 日历</h2>
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
              <FontAwesomeIcon icon={faChevronLeft} className={`collapse-icon ${isCollapsed ? 'rotate' : ''}`} />
            </button>
          )}
        </div>
        <nav className="sidebar-menu">
          <ul>
            {menuItems.filter(item => {
              // 对于 /admin 路径，使用user?.role判断
              if (item.to === "/admin") {
                return isAuthenticated && (user?.role === 'admin' || user?.role === 'manager');
              }
              // 对于其他需要权限的项，使用hasPermission
              if (item.permission === null) return true;
              if (item.permission === 'authenticated') return isAuthenticated;
              
              if (Array.isArray(item.permission)) {
                return item.permission.some(role => user?.role === role);
              }
              return hasPermission(item.permission);
            }).map(renderMenuItem)}
          </ul>
        </nav>
      </div>
      {!isMobileMenuOpen && (
        <button className="mobile-menu-toggle" onClick={toggleMobileMenu}>
          <FontAwesomeIcon icon={faBars} />
        </button>
      )}
    </>
  );
};

export default Sidebar;
