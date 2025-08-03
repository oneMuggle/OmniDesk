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
   const [showCalendarSubMenu, setShowCalendarSubMenu] = useState(false); // 新增日历子菜单状态
   const { user, isAuthenticated, logout, isGuest, hasPermission } = useAuth();
   const location = useLocation();

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
            {[
              { to: "/", icon: faHome, text: "首页", permission: null },
              // { to: "/calendar", icon: faCalendarAlt, text: "日历", permission: null }, // 移除一级日历链接
              { to: "/events", icon: faTasks, text: "事件", permission: "events.manage_schedule" },
              { to: "/profile", icon: faUser, text: "个人资料", permission: null },
              { to: "/announcements", icon: faBullhorn, text: "公告栏", permission: "events.manage_announcements" },
              { to: "/deepseek-chat", icon: faCommentDots, text: "DeepSeek聊天", permission: null },
              { to: "/file-analysis", icon: faFileAlt, text: "文件分析", permission: null },
              { to: "/library", icon: faBook, text: "书库", permission: null },
              { to: "/docs/cdepsio6", icon: faFileAlt, text: "文档", permission: null },
              { to: "/admin", icon: faCog, text: "管理中心", permission: ["admin", "manager"] } // 新增管理中心链接
            ].filter(item => {
              if (item.to === "/admin") {
                return isAuthenticated && (user?.role === 'admin' || user?.role === 'manager');
              }
              if (item.permission === null) {
                return true;
              }
              if (Array.isArray(item.permission)) {
                return item.permission.some(p => hasPermission(p));
              }
              return hasPermission(item.permission);
            }).map((item, index) => (
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
            ))}
            {/* 新增日历一级菜单和二级子菜单 */}
            <li>
              <div
                className={`menu-item ${location.pathname.startsWith('/trial-calendar') || location.pathname.startsWith('/shift-calendar') ? 'active' : ''}`}
                onClick={() => setShowCalendarSubMenu(!showCalendarSubMenu)}
                title={isCollapsed ? "日历" : ''}
              >
                <div className="menu-item-content">
                  <FontAwesomeIcon icon={faCalendarAlt} className="icon" />
                  {!isCollapsed && (
                    <>
                      <span>日历</span>
                      <FontAwesomeIcon icon={faChevronDown} className={`submenu-arrow ${showCalendarSubMenu ? 'expanded' : ''}`} />
                    </>
                  )}
                </div>
              </div>
              {showCalendarSubMenu && (
                <ul className="submenu">
                  <li>
                    <Link
                      to="/trial-calendar"
                      className={`menu-item ${location.pathname === '/trial-calendar' ? 'active' : ''}`}
                      onClick={() => isMobileMenuOpen && toggleMobileMenu()}
                      title={isCollapsed ? "试验日历" : ''}
                    >
                      <div className="menu-item-content">
                        {!isCollapsed && <span>试验日历</span>}
                      </div>
                    </Link>
                  </li>
                  <li>
                    <Link
                      to="/shift-calendar"
                      className={`menu-item ${location.pathname === '/shift-calendar' ? 'active' : ''}`}
                      onClick={() => isMobileMenuOpen && toggleMobileMenu()}
                      title={isCollapsed ? "排班日历" : ''}
                    >
                      <div className="menu-item-content">
                        {!isCollapsed && <span>排班日历</span>}
                      </div>
                    </Link>
                  </li>
                </ul>
              )}
            </li>
            <li>
              <button
                className="menu-item"
                onClick={() => {
                  logout();
                  if (isMobileMenuOpen) toggleMobileMenu();
                }}
              >
                <FontAwesomeIcon icon={faSignOutAlt} className="icon" />
                退出登录
              </button>
            </li>
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
