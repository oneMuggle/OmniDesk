import React, { useState, useEffect } from 'react';
import { Link, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { permissionsApi } from '../../api/permissionsApi';
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
  faCaretRight, // For dropdown indicator
  faCalendarAlt,
  faUserShield,
  faNewspaper
} from '@fortawesome/free-solid-svg-icons';
import ProtectedRoute from '../ProtectedRoute';

const allAdminMenuItems = [
  { to: "/control-panel/trials", icon: faFlask, text: "试验管理", permission: "events.view_trial" },
  { to: "/control-panel/personnel", icon: faUsers, text: "人员管理", permission: "personnel.view_personnel" },
  { to: "/control-panel/schedules", icon: faFlask, text: "排班管理", permission: "events.view_schedule" },
  { to: "/control-panel/user-management", icon: faUsers, text: "用户管理", permission: "users.view_customuser" },
  { to: "/control-panel/ebook-management", icon: faBook, text: "电子书管理", permission: "documents.view_ebook" },
  { to: "/control-panel/documents", icon: faFileWord, text: "文档管理", permission: "documents.view_documenttemplate" },
  { to: "/control-panel/equipment", icon: faFlask, text: "设备管理", permission: "events.view_equipment" },
  { to: "/control-panel/settings", icon: faCog, text: "设置", permission: "config.view_page" },
  { to: "/control-panel/announcements", icon: faBullhorn, text: "公告管理", permission: "events.view_announcement" },
  { to: "/control-panel/dify-app-management", icon: faCog, text: "Dify 应用管理", permission: "dify_apps.view_difyapp" },
  { to: "/control-panel/schedule-settings", icon: faCog, text: "排班设置", permission: "events.view_schedulesetting" },
  { to: "/control-panel/meeting-room-management", icon: faCog, text: "会议室管理", permission: "meeting_rooms.view_meetingroom" },
  { to: "/control-panel/holidays", icon: faCalendarAlt, text: "节假日管理", permission: "events.view_holiday" },
  { to: "/control-panel/news-stats", icon: faNewspaper, text: "新闻统计", permission: "news.view_news" },
  { to: "/control-panel/news-management", icon: faNewspaper, text: "新闻管理", permission: "news.view_news" }
];

const AdminLayout = () => {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [openSubmenu, setOpenSubmenu] = useState(null);
  const { user, isAuthenticated, logout, hasPermission } = useAuth();
  const location = useLocation();

  const menuItems = React.useMemo(() => {
    if (isAuthenticated && user) {
      return allAdminMenuItems.filter(item =>
        item.permission ? hasPermission(item.permission) : true
      );
    }
    return [];
  }, [isAuthenticated, user, hasPermission]);


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
            {(menuItems || []).map((item, index) => (
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