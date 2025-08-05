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
  faChevronDown // 新增图标
} from '@fortawesome/free-solid-svg-icons';
 
const Sidebar = ({ isMobileMenuOpen, toggleMobileMenu }) => {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [showCalendarSubMenu, setShowCalendarSubMenu] = useState(false);
  const { user, isAuthenticated, logout, hasPermission } = useAuth();
  const location = useLocation();

  const menuItems = [
    { to: "/", icon: faHome, text: "首页", permission: null },
    { to: "/announcements", icon: faBullhorn, text: "公告栏", permission: "events.manage_announcements" },
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
    { to: "/deepseek-chat", icon: faCommentDots, text: "DeepSeek聊天", permission: null },
    { to: "/docs/cdepsio6", icon: faFileAlt, text: "文档", permission: null },
    { to: "/file-analysis", icon: faFileAlt, text: "文件分析", permission: null },
    { to: "/library", icon: faBook, text: "书库", permission: null },
    { to: "/profile", icon: faUser, text: "个人资料", permission: null },
    { to: "/admin", icon: faCog, text: "管理中心", permission: ["admin", "manager"] },
    { type: 'button', icon: faSignOutAlt, text: '退出登录', action: logout, permission: 'authenticated' }
  ];

  const renderMenuItem = (item, index) => {
    if (item.type === 'button') {
      if (item.permission === 'authenticated' && !isAuthenticated) return null;
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
      const isActive = item.subItems.some(sub => location.pathname === sub.to);
      return (
        <li key={index}>
          <div
            className={`menu-item ${isActive ? 'active' : ''}`}
            onClick={() => setShowCalendarSubMenu(!showCalendarSubMenu)}
            title={isCollapsed ? item.text : ''}
          >
            <div className="menu-item-content">
              <FontAwesomeIcon icon={item.icon} className="icon" />
              {!isCollapsed && (
                <>
                  <span>{item.text}</span>
                  <FontAwesomeIcon icon={faChevronDown} className={`submenu-arrow ${showCalendarSubMenu ? 'expanded' : ''}`} />
                </>
              )}
            </div>
          </div>
          {showCalendarSubMenu && !isCollapsed && (
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
              if (item.permission === null) return true;
              if (item.permission === 'authenticated') return isAuthenticated;
              if (item.to === "/admin") {
                return isAuthenticated && (user?.role === 'admin' || user?.role === 'manager');
              }
              if (Array.isArray(item.permission)) {
                return item.permission.some(p => hasPermission(p));
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
