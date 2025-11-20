import React, { useState } from 'react';
import { Link, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import './AdminLayout.css';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import {
  faFlask,
  faUsers,
  faBook,
  faCog,
  faChevronLeft,
  faFileWord,
  faBars,
  faSignOutAlt,
  faHome,
  faBullhorn,
  faCaretDown, // For dropdown indicator
  faCaretRight // For dropdown indicator
} from '@fortawesome/free-solid-svg-icons';
import ProtectedRoute from '../ProtectedRoute';

const AdminLayout = () => {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [openSubmenu, setOpenSubmenu] = useState(null); // State to manage open submenu
  const { user, isAuthenticated, logout, hasPermission } = useAuth();
  const location = useLocation();

  // 检查用户是否具有admin或manager权限
  const canAccessAdmin = isAuthenticated && (user?.role === 'admin' || user?.role === 'manager');

  if (!canAccessAdmin) {
    // 如果没有权限，则重定向到未授权页面或登录页面
    return <ProtectedRoute roles={['admin', 'manager']}><div></div></ProtectedRoute>;
  }

  const adminMenuItems = [
    { to: "/admin/trials", icon: faFlask, text: "试验管理", permission: ['admin', 'manager'] },
    { to: "/admin/personnel", icon: faUsers, text: "人员管理", permission: ['admin', 'manager'] },
    { to: "/admin/schedules", icon: faFlask, text: "排班管理", permission: ['admin', 'manager'] },
    { to: "/admin/user-management", icon: faUsers, text: "用户管理", permission: ['admin'] },
    { to: "/admin/ebook-management", icon: faBook, text: "电子书管理", permission: ['admin', 'manager'] },
    { to: "/admin/documents", icon: faFileWord, text: "文档管理", permission: ['admin', 'manager'] },
    { to: "/admin/equipment", icon: faFlask, text: "设备管理", permission: ['admin', 'manager'] },
    { to: "/admin/settings", icon: faCog, text: "设置", permission: ['admin', 'manager'] }, // 假设设置也放在这里，且需要admin/manager权限
    { to: "/admin/announcements", icon: faBullhorn, text: "公告管理", permission: ['admin', 'manager'] },
    { to: "/admin/dify-app-management", icon: faCog, text: "Dify 应用管理", permission: ['admin', 'manager'] },
    { to: "/admin/schedule-settings", icon: faCog, text: "排班设置", permission: ['admin', 'manager'] },
    { to: "/admin/user-personnel-management", icon: faUsers, text: "用户人员关联管理", permission: ["admin", "manager"] },
    { to: "/admin/meeting-room-management", icon: faCog, text: "会议室管理", permission: ['admin', 'manager'] }
  ];

  return (
    <div className="admin-layout">
      <div className={`admin-sidebar ${isCollapsed ? 'collapsed' : ''}`}>
        <div className="admin-sidebar-header">
          <h2>管理面板</h2>
          <button
            className="collapse-toggle"
            onClick={() => setIsCollapsed(!isCollapsed)}
          >
            <FontAwesomeIcon icon={faChevronLeft} className={`collapse-icon ${isCollapsed ? 'rotate' : ''}`} />
          </button>
        </div>
        <nav className="admin-sidebar-menu">
          <ul>
            {adminMenuItems.filter(item => {
              if (!item.permission) return true; // 如果没有定义权限，则默认显示
              if (Array.isArray(item.permission)) {
                return item.permission.some(p => user?.role === p);
              }
              return user?.role === item.permission;
            }).map((item, index) => (
              <li key={index}>
                {item.children ? (
                  <div
                    className={`menu-item ${location.pathname.startsWith(item.to) ? 'active' : ''} ${openSubmenu === item.text ? 'open' : ''}`}
                    onClick={() => setOpenSubmenu(openSubmenu === item.text ? null : item.text)}
                    title={isCollapsed ? item.text : ''}
                  >
                    <div className="menu-item-content">
                      <FontAwesomeIcon icon={item.icon} className="icon" />
                      {!isCollapsed && <span>{item.text}</span>}
                      {!isCollapsed && (
                        <FontAwesomeIcon
                          icon={openSubmenu === item.text ? faCaretDown : faCaretRight}
                          className="submenu-caret"
                        />
                      )}
                    </div>
                  </div>
                ) : (
                  <Link
                    to={item.to}
                    className={`menu-item ${location.pathname === item.to ? 'active' : ''}`}
                    title={isCollapsed ? item.text : ''}
                  >
                    <div className="menu-item-content">
                      <FontAwesomeIcon icon={item.icon} className="icon" />
                      {!isCollapsed && <span>{item.text}</span>}
                    </div>
                  </Link>
                )}
                {item.children && openSubmenu === item.text && (
                  <ul className="submenu">
                    {item.children.map((subItem, subIndex) => (
                      <li key={subIndex}>
                        <Link
                          to={subItem.to}
                          className={`submenu-item ${location.pathname === subItem.to ? 'active' : ''}`}
                          title={isCollapsed ? subItem.text : ''}
                        >
                          {!isCollapsed && <span>{subItem.text}</span>}
                        </Link>
                      </li>
                    ))}
                  </ul>
                )}
              </li>
            ))}
            <li>
              <Link to="/" className="menu-item">
                <FontAwesomeIcon icon={faHome} className="icon" />
                {!isCollapsed && <span>返回主页</span>}
              </Link>
            </li>
            <li>
              <button
                className="menu-item"
                onClick={logout}
              >
                <FontAwesomeIcon icon={faSignOutAlt} className="icon" />
                {!isCollapsed && <span>退出登录</span>}
              </button>
            </li>
          </ul>
        </nav>
      </div>
      <div className="admin-content">
        <Outlet />
      </div>
    </div>
  );
};

export default AdminLayout;