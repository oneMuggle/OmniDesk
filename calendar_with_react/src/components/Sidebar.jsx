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
  faFileAlt
} from '@fortawesome/free-solid-svg-icons';

const Sidebar = ({ isMobileMenuOpen, toggleMobileMenu }) => {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const { isAuthenticated, logout, hasPermission, isGuest } = useAuth();
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
              { to: "/calendar", icon: faCalendarAlt, text: "日历", permission: null },
              { to: "/settings", icon: faCog, text: "设置", permission: null },
              { to: "/events", icon: faTasks, text: "事件", permission: "manage_schedule" },
              { to: "/profile", icon: faUser, text: "个人资料", permission: null },
              { to: "/documents", icon: faFileWord, text: "文档管理", permission: null },
              { to: "/trials", icon: faFlask, text: "试验管理", permission: null },
              { to: "/equipment", icon: faFlask, text: "设备管理", permission: "manage_equipment" },
              { to: "/personnel", icon: faUsers, text: "人员管理", permission: "manage_personnel" },
              { to: "/announcements", icon: faBullhorn, text: "公告栏", permission: "manage_announcements" },
              { to: "/deepseek-chat", icon: faCommentDots, text: "DeepSeek聊天", permission: null },
              { to: "/file-analysis", icon: faFileAlt, text: "文件分析", permission: null }
            ].filter(item => 
              item.permission === null || 
              (isAuthenticated && hasPermission(item.permission)) || 
              isGuest
            ).map((item, index) => (
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
