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

const AdminLayout = () => {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [openSubmenu, setOpenSubmenu] = useState(null);
  const [menuItems, setMenuItems] = useState([]);
  const { user, isAuthenticated, logout } = useAuth();
  const location = useLocation();

  const allAdminMenuItems = [
    { to: "/admin/trials", icon: faFlask, text: "试验管理", path: "/admin/trials" },
    { to: "/admin/personnel", icon: faUsers, text: "人员管理", path: "/admin/personnel" },
    { to: "/admin/schedules", icon: faFlask, text: "排班管理", path: "/admin/schedules" },
    { to: "/admin/user-management", icon: faUsers, text: "用户管理", path: "/admin/user-management" },
    { to: "/admin/permissions", icon: faUserShield, text: "权限管理", path: "/admin/permissions" },
    { to: "/admin/ebook-management", icon: faBook, text: "电子书管理", path: "/admin/ebook-management" },
    { to: "/admin/documents", icon: faFileWord, text: "文档管理", path: "/admin/documents" },
    { to: "/admin/equipment", icon: faFlask, text: "设备管理", path: "/admin/equipment" },
    { to: "/admin/settings", icon: faCog, text: "设置", path: "/admin/settings" },
    { to: "/admin/announcements", icon: faBullhorn, text: "公告管理", path: "/admin/announcements" },
    { to: "/admin/dify-app-management", icon: faCog, text: "Dify 应用管理", path: "/admin/dify-app-management" },
    { to: "/admin/schedule-settings", icon: faCog, text: "排班设置", path: "/admin/schedule-settings" },
    { to: "/admin/meeting-room-management", icon: faCog, text: "会议室管理", path: "/admin/meeting-room-management" },
    { to: "/admin/holidays", icon: faCalendarAlt, text: "节假日管理", path: "/admin/holidays" },
    { to: "/admin/news-stats", icon: faNewspaper, text: "新闻统计", path: "/admin/news-stats" },
    { to: "/admin/news-management", icon: faNewspaper, text: "新闻管理", path: "/admin/news-management" }
  ];

  useEffect(() => {
    const fetchPermissionsAndSetMenu = async () => {
      if (user?.role === 'admin') {
        setMenuItems(allAdminMenuItems);
        return;
      }

      try {
        const userPermissions = await permissionsApi.getMyPermissions();
        const allowedPaths = userPermissions.map(p => p.path);
        const filteredMenuItems = allAdminMenuItems.filter(item => allowedPaths.includes(item.path));
        setMenuItems(filteredMenuItems);
      } catch (error) {
        console.error("Failed to fetch user permissions:", error);
        setMenuItems([]); // Or handle error appropriately
      }
    };

    if (isAuthenticated) {
      fetchPermissionsAndSetMenu();
    }
  }, [isAuthenticated, user]);

  const canAccessAdmin = isAuthenticated && (user?.role === 'admin' || user?.role === 'manager');

  if (!canAccessAdmin) {
    return <ProtectedRoute roles={['admin', 'manager']}><div></div></ProtectedRoute>;
  }

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
            {menuItems.map((item, index) => (
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